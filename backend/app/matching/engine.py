"""The scoring engine: rank open jobs against a parsed intent and explain why.

Scoring model
-------------
Seven independent signals, each normalised to 0-1, combined as a weighted mean:

    semantic       0.25   TF-IDF cosine between the query and the job document
    skills         0.25   overlap between requested and required skills
    role_type      0.15   backend / frontend / data science / devops / ...
    domain         0.15   business domain (healthcare, fintech, ...)
    location       0.10   city / work mode fit
    experience     0.07   seniority band fit
    company_stage  0.03   startup vs midsize vs enterprise

A signal the query said nothing about is switched off and its weight is
redistributed across the signals that *are* active. Without that, asking
"remote Python job" would silently penalise every listing for not matching a
domain the candidate never mentioned.

Why a weighted ensemble instead of one model? Because each signal fails in a
different way. TF-IDF alone matches on vocabulary and will happily rank a
"Python" job in Mumbai above one in the candidate's own city. Exact filters
alone are brittle and return nothing when the phrasing is unusual. Blending
them means the exact signals give precision and the fuzzy one gives recall.
"""

from dataclasses import dataclass

from app.matching.parser import Intent
from app.matching.taxonomy import (
    DOMAIN_LOOKUP,
    EXPERIENCE_BANDS,
    EXPERIENCE_ORDER,
    LOCATION_LOOKUP,
    ROLE_TYPE_LOOKUP,
    SKILL_LOOKUP,
)
from app.matching.text import normalize
from app.matching.tfidf import TfidfIndex

WEIGHTS: dict[str, float] = {
    "semantic": 0.25,
    "skills": 0.25,
    "role_type": 0.15,
    "domain": 0.15,
    "location": 0.10,
    "experience": 0.07,
    "company_stage": 0.03,
}

# Cosine similarity between a one-sentence query and a full job description
# rarely exceeds ~0.45 even for an ideal match, because the description carries
# far more vocabulary than the query. Dividing by this calibration constant
# maps a realistic best case onto 1.0 instead of leaving every score bunched
# near the bottom of the range. The value came from eyeballing the seed corpus.
SEMANTIC_CALIBRATION = 0.45


@dataclass
class ScoredJob:
    job: object
    score: float
    breakdown: dict[str, float]
    reasons: list[str]
    explanation: str
    matched_skills: list[str]
    missing_skills: list[str]


def job_document(job) -> str:
    """Flatten a job into the single text blob the vectoriser sees.

    Title, skills and domain are repeated because term frequency is what TF-IDF
    weighs - stating them more than once is a blunt but effective way of saying
    "these fields matter more than the body copy".
    """
    skills = " ".join(job.required_skills or [])
    return " ".join(
        [
            job.title,
            job.title,
            skills,
            skills,
            job.domain or "",
            job.domain or "",
            job.company_name or "",
            job.location or "",
            job.work_mode or "",
            job.company_stage or "",
            job.experience_level or "",
            job.description or "",
        ]
    )


def _canonicalize(values: list[str], lookup: list[tuple[str, str]]) -> set[str]:
    """Map free-text values onto canonical taxonomy labels."""
    out: set[str] = set()
    for value in values or []:
        text = normalize(value)
        if not text:
            continue
        for surface, canonical in lookup:
            if surface == text:
                out.add(canonical)
                break
        else:
            out.add(value.strip())
    return out


# --------------------------------------------------------------------------- #
# Individual signals. Each returns (score in 0-1, active?)
# --------------------------------------------------------------------------- #
def _score_skills(intent: Intent, job) -> tuple[float, bool, list[str], list[str]]:
    wanted = _canonicalize(intent.skills, SKILL_LOOKUP)
    required = _canonicalize(job.required_skills or [], SKILL_LOOKUP)

    if not wanted or not required:
        return 0.0, False, [], sorted(required - wanted)

    matched = wanted & required
    # Two views of the same overlap, blended:
    #   recall  - of the skills the candidate asked for, how many does this job want?
    #   coverage- of the skills this job requires, how many does the candidate have?
    # Recall is weighted higher because the candidate's stated intent is the
    # thing being served; coverage stops a job that requires 15 skills from
    # scoring as highly as one that requires exactly the 3 they named.
    recall = len(matched) / len(wanted)
    coverage = len(matched) / len(required)
    score = 0.70 * recall + 0.30 * coverage

    return score, True, sorted(matched), sorted(required - wanted)


def infer_role_types(job) -> list[str]:
    """Work out what kind of role a listing is from its title, then its body.

    Jobs have no explicit `role_type` column - an admin posting a job should not
    have to pick from a taxonomy dropdown that will always be incomplete. The
    title carries this signal reliably ("Senior Backend Engineer"), so it is
    checked first and the description is only a fallback.
    """
    from app.matching.parser import _find_all  # local import avoids a cycle

    found = _find_all(normalize(job.title), ROLE_TYPE_LOOKUP, limit=3)
    if found:
        return found
    return _find_all(normalize(job.description or ""), ROLE_TYPE_LOOKUP, limit=2)


# Roles that share most of their day-to-day work. A backend-shaped query should
# not score a full-stack listing as a total miss.
_ADJACENT_ROLES: dict[str, set[str]] = {
    "Backend": {"Full Stack", "DevOps", "Data Engineering"},
    "Frontend": {"Full Stack", "Mobile", "Design"},
    "Full Stack": {"Backend", "Frontend"},
    "Data Science": {"Data Engineering", "Data Analysis"},
    "Data Engineering": {"Data Science", "Data Analysis", "Backend"},
    "Data Analysis": {"Data Science", "Data Engineering", "Product"},
    "DevOps": {"Backend", "Security"},
    "Mobile": {"Frontend", "Full Stack"},
    "QA": {"Backend", "Frontend"},
    "Security": {"DevOps", "Backend"},
    "Product": {"Design", "Data Analysis", "Management"},
    "Design": {"Frontend", "Product"},
    "Management": {"Backend", "Product"},
}


def _score_role_type(intent: Intent, job) -> tuple[float, bool]:
    if not intent.role_types:
        return 0.0, False

    job_roles = set(infer_role_types(job))
    if not job_roles:
        # The listing did not name a discipline; stay neutral rather than
        # punishing it for a taxonomy gap that is our fault, not the job's.
        return 0.5, True

    wanted = set(intent.role_types)
    if wanted & job_roles:
        return 1.0, True

    # Adjacent discipline - a real but weaker fit.
    for role in wanted:
        if _ADJACENT_ROLES.get(role, set()) & job_roles:
            return 0.45, True

    return 0.05, True


def _score_domain(intent: Intent, job) -> tuple[float, bool]:
    if not intent.domains:
        return 0.0, False

    wanted = set(intent.domains)
    job_domain = _canonicalize([job.domain], DOMAIN_LOOKUP) if job.domain else set()

    if wanted & job_domain:
        return 1.0, True

    # The structured field did not match, but the description might still be
    # about that domain. Partial credit rather than a hard zero.
    haystack = normalize(f"{job.description} {job.company_name} {job.title}")
    for canonical in wanted:
        for surface, mapped in DOMAIN_LOOKUP:
            if mapped == canonical and surface in haystack:
                return 0.55, True
    return 0.0, True


def _score_location(intent: Intent, job) -> tuple[float, bool]:
    wants_location = bool(intent.locations)
    wants_mode = bool(intent.work_modes)
    if not wants_location and not wants_mode:
        return 0.0, False

    parts: list[float] = []

    if wants_location:
        wanted = set(intent.locations)
        job_location = _canonicalize([job.location], LOCATION_LOOKUP)
        if wanted & job_location:
            parts.append(1.0)
        elif job.work_mode == "remote":
            # A remote job satisfies almost any city preference.
            parts.append(0.85)
        else:
            parts.append(0.10)

    if wants_mode:
        if job.work_mode in intent.work_modes:
            parts.append(1.0)
        elif job.work_mode == "hybrid" and "remote" in intent.work_modes:
            # Hybrid is a near miss for someone who asked for remote.
            parts.append(0.5)
        else:
            parts.append(0.15)

    return sum(parts) / len(parts), True


def _score_experience(intent: Intent, job) -> tuple[float, bool]:
    if not intent.experience_levels and intent.years_experience is None:
        return 0.0, False

    scores: list[float] = []

    if intent.experience_levels:
        job_index = (
            EXPERIENCE_ORDER.index(job.experience_level)
            if job.experience_level in EXPERIENCE_ORDER
            else 1
        )
        best = 0.0
        for level in intent.experience_levels:
            if level not in EXPERIENCE_ORDER:
                continue
            distance = abs(EXPERIENCE_ORDER.index(level) - job_index)
            # One band apart is a realistic stretch; two bands is a bad fit.
            best = max(best, {0: 1.0, 1: 0.6, 2: 0.25}.get(distance, 0.0))
        scores.append(best)

    if intent.years_experience is not None:
        low, high = EXPERIENCE_BANDS.get(job.experience_level, (0.0, 30.0))
        low = max(low, job.min_years_experience or 0.0)
        years = intent.years_experience
        if low <= years <= high:
            scores.append(1.0)
        else:
            # Linear decay: one year outside the band costs 25%.
            gap = low - years if years < low else years - high
            scores.append(max(0.0, 1.0 - 0.25 * gap))

    return (sum(scores) / len(scores)) if scores else 0.0, True


def _score_company_stage(intent: Intent, job) -> tuple[float, bool]:
    if not intent.company_stages:
        return 0.0, False
    if job.company_stage in intent.company_stages:
        return 1.0, True
    # Adjacent stages are a partial fit; startup vs enterprise is not.
    order = ["startup", "midsize", "enterprise"]
    if job.company_stage in order:
        job_index = order.index(job.company_stage)
        best = 0.0
        for stage in intent.company_stages:
            if stage in order:
                distance = abs(order.index(stage) - job_index)
                best = max(best, {0: 1.0, 1: 0.4}.get(distance, 0.05))
        return best, True
    return 0.0, True


# --------------------------------------------------------------------------- #
# Explanation
# --------------------------------------------------------------------------- #
def _build_reasons(
    intent: Intent,
    job,
    breakdown: dict[str, float],
    matched_skills: list[str],
    missing_skills: list[str],
    semantic_terms: list[str],
) -> list[str]:
    """Turn the numeric breakdown into short human-readable bullet points."""
    reasons: list[str] = []

    if matched_skills:
        shown = ", ".join(matched_skills[:5])
        more = f" (+{len(matched_skills) - 5} more)" if len(matched_skills) > 5 else ""
        reasons.append(f"Skills overlap: {shown}{more}.")

    if breakdown["role_type"] >= 0.9 and intent.role_types:
        reasons.append(f"This is a {intent.role_types[0].lower()} role, which is what you asked for.")
    elif 0.3 <= breakdown["role_type"] < 0.9 and intent.role_types:
        job_roles = infer_role_types(job)
        if job_roles:
            reasons.append(
                f"Adjacent discipline: the listing is a {job_roles[0].lower()} role rather than "
                f"{intent.role_types[0].lower()}."
            )

    if breakdown["domain"] >= 0.9 and job.domain:
        reasons.append(f"Works in {job.domain}, which is what you asked for.")
    elif breakdown["domain"] >= 0.4 and intent.domains:
        reasons.append(
            f"The role description touches {intent.domains[0]}, though the listing is filed under "
            f"{job.domain or 'no specific domain'}."
        )

    if breakdown["location"] >= 0.9:
        if job.work_mode == "remote":
            reasons.append("Fully remote, so location is not a constraint.")
        else:
            reasons.append(f"Based in {job.location}, matching your location preference.")
    elif breakdown["location"] >= 0.5:
        reasons.append(f"{job.work_mode.title()} in {job.location} - a partial fit for what you asked.")

    if breakdown["experience"] >= 0.9:
        reasons.append(f"Seniority fits: this is a {job.experience_level}-level role.")
    elif 0.4 <= breakdown["experience"] < 0.9:
        reasons.append(f"Close on seniority - the listing is pitched at {job.experience_level} level.")

    if breakdown["company_stage"] >= 0.9:
        reasons.append(f"{job.company_name or 'The company'} is a {job.company_stage}, as requested.")

    if semantic_terms and len(reasons) < 4:
        reasons.append(f"Wording overlap on: {', '.join(semantic_terms[:4])}.")

    if missing_skills:
        shown = ", ".join(missing_skills[:4])
        reasons.append(f"Gap to close: the listing also asks for {shown}.")

    if not reasons:
        reasons.append("Ranked on overall description similarity - no specific signal matched strongly.")

    return reasons


def _build_explanation(score: float, job, reasons: list[str]) -> str:
    """One-sentence headline shown above the bullet points."""
    if score >= 75:
        strength = "Strong match"
    elif score >= 55:
        strength = "Good match"
    elif score >= 35:
        strength = "Partial match"
    else:
        strength = "Weak match"

    lead = reasons[0].rstrip(".") if reasons else "ranked on overall similarity"
    return f"{strength} ({score:.0f}%) for {job.title} at {job.company_name or 'this company'} - {lead[0].lower()}{lead[1:]}."


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def rank_jobs(intent: Intent, jobs: list, limit: int = 10) -> list[ScoredJob]:
    """Score every job against the intent and return the best `limit` of them."""
    if not jobs:
        return []

    index = TfidfIndex([job_document(job) for job in jobs])
    # The query fed to TF-IDF is the raw text plus the canonical labels the
    # parser recognised. Adding the labels means "healthtech" in the query can
    # still align with a job that literally says "healthcare".
    query_text = " ".join(
        [intent.raw_query]
        + intent.skills
        + intent.domains
        + intent.role_types
        + intent.locations
    )
    query_vector = index.vectorize_query(query_text)

    scored: list[ScoredJob] = []
    for position, job in enumerate(jobs):
        cosine = index.similarity(query_vector, position)
        semantic = min(1.0, cosine / SEMANTIC_CALIBRATION)

        skills_score, skills_active, matched_skills, missing_skills = _score_skills(intent, job)
        role_score, role_active = _score_role_type(intent, job)
        domain_score, domain_active = _score_domain(intent, job)
        location_score, location_active = _score_location(intent, job)
        experience_score, experience_active = _score_experience(intent, job)
        stage_score, stage_active = _score_company_stage(intent, job)

        signals = {
            "semantic": (semantic, True),
            "skills": (skills_score, skills_active),
            "role_type": (role_score, role_active),
            "domain": (domain_score, domain_active),
            "location": (location_score, location_active),
            "experience": (experience_score, experience_active),
            "company_stage": (stage_score, stage_active),
        }

        # Weighted mean over active signals only.
        active_weight = sum(WEIGHTS[name] for name, (_, active) in signals.items() if active)
        total = sum(
            WEIGHTS[name] * value for name, (value, active) in signals.items() if active
        )
        final = (total / active_weight) if active_weight else 0.0
        score = round(final * 100, 1)

        breakdown = {name: round(value, 3) for name, (value, _) in signals.items()}
        semantic_terms = index.top_overlapping_terms(query_vector, position)
        reasons = _build_reasons(intent, job, breakdown, matched_skills, missing_skills, semantic_terms)

        scored.append(
            ScoredJob(
                job=job,
                score=score,
                breakdown=breakdown,
                reasons=reasons,
                explanation=_build_explanation(score, job, reasons),
                matched_skills=matched_skills,
                missing_skills=missing_skills,
            )
        )

    # Sort by score, then newest first so ties are stable and sensible.
    scored.sort(key=lambda item: (item.score, item.job.id), reverse=True)
    # Drop near-zero results rather than padding the list with noise, but always
    # return something if anything scored at all.
    meaningful = [item for item in scored if item.score >= 15]
    return (meaningful or scored)[:limit]
