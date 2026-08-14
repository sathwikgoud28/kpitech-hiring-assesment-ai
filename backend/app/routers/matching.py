"""AI matching endpoint.

Open to anonymous callers so the feature can be demoed without signing in.
When a candidate *is* signed in and opts in, their saved profile is blended
into the parsed intent.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_optional_user
from app.matching import enrich_with_profile, llm, parse_query, rank_jobs
from app.models import CandidateProfile, Job, JobStatus, User, UserRole
from app.schemas import (
    JobOut,
    MatchRequest,
    MatchResponse,
    MatchResult,
    ParsedIntent,
    ScoreBreakdown,
)

router = APIRouter(prefix="/api/match", tags=["ai-matching"])


@router.post("", response_model=MatchResponse)
def match_jobs(
    payload: MatchRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> MatchResponse:
    """Rank currently-open jobs against a natural-language description.

    Only OPEN jobs are considered - the brief says the system matches "from
    what is currently posted", and surfacing a closed listing would waste the
    candidate's time.
    """
    intent = parse_query(payload.query)

    used_profile = False
    if payload.use_profile and user is not None and user.role == UserRole.CANDIDATE.value:
        profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        if profile is not None and (profile.skills or profile.domain_interests):
            intent = enrich_with_profile(intent, profile)
            used_profile = True

    open_jobs = list(
        db.scalars(select(Job).where(Job.status == JobStatus.OPEN.value)).all()
    )

    # Stage 1 - deterministic retrieval. This always runs and always succeeds.
    ranked = rank_jobs(intent, open_jobs, limit=payload.limit)

    # Stage 2 - optional LLM re-rank over the shortlist. Any failure returns
    # None and leaves stage 1 untouched.
    llm_used = False
    verdicts = llm.rerank(payload.query, intent, ranked) if payload.use_llm else None

    results = [_to_result(item) for item in ranked]
    if verdicts:
        results = _blend(results, verdicts)
        llm_used = True

    return MatchResponse(
        query=payload.query,
        parsed=ParsedIntent(
            skills=intent.skills,
            domains=intent.domains,
            locations=intent.locations,
            role_types=intent.role_types,
            work_modes=intent.work_modes,
            company_stages=intent.company_stages,
            experience_levels=intent.experience_levels,
        ),
        used_profile=used_profile,
        total_open_jobs=len(open_jobs),
        results=results,
        llm_used=llm_used,
        llm_model=llm.model_name() if llm_used else None,
        llm_available=llm.is_available(),
    )


def _to_result(item) -> MatchResult:
    """Deterministic result, before any LLM involvement."""
    return MatchResult(
        job=JobOut.model_validate(item.job),
        score=item.score,
        explanation=item.explanation,
        reasons=item.reasons,
        matched_skills=item.matched_skills,
        missing_skills=item.missing_skills,
        breakdown=ScoreBreakdown(**item.breakdown),
    )


def _blend(results: list[MatchResult], verdicts: list) -> list[MatchResult]:
    """Merge LLM judgements into the deterministic results and re-sort.

    The final score is a weighted average of the two, rather than the LLM's
    number alone. The deterministic engine contributes signals the model cannot
    see reliably (exact skill set membership, precise seniority bands), and the
    model contributes language understanding the taxonomy lacks. Keeping both
    also means a wild LLM score can only move a result so far.

    Results the model did not return keep their deterministic score untouched.
    """
    weight = settings.llm_blend_weight
    by_id = {verdict.job_id: verdict for verdict in verdicts}

    for result in results:
        verdict = by_id.get(result.job.id)
        if verdict is None:
            continue
        result.engine_score = result.score
        result.llm_relevance = round(verdict.relevance, 1)
        result.score = round((1 - weight) * result.score + weight * verdict.relevance, 1)
        if verdict.explanation:
            result.explanation = verdict.explanation
        if verdict.reasons:
            result.reasons = verdict.reasons

    results.sort(key=lambda r: (r.score, r.job.id), reverse=True)
    return results
