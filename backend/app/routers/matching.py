"""AI matching endpoint.

Open to anonymous callers so the feature can be demoed without signing in.
When a candidate *is* signed in and opts in, their saved profile is blended
into the parsed intent.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_optional_user
from app.matching import enrich_with_profile, parse_query, rank_jobs
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
    ranked = rank_jobs(intent, open_jobs, limit=payload.limit)

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
        results=[
            MatchResult(
                job=JobOut.model_validate(item.job),
                score=item.score,
                explanation=item.explanation,
                reasons=item.reasons,
                matched_skills=item.matched_skills,
                missing_skills=item.missing_skills,
                breakdown=ScoreBreakdown(**item.breakdown),
            )
            for item in ranked
        ],
    )
