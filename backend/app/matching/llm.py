"""Optional LLM re-ranking layer (Llama 3.3 served by Groq).

Why this exists
---------------
The deterministic engine in `engine.py` only understands vocabulary that lives
in `taxonomy.py`. A genuinely novel phrasing - "I want to work on models that
read doctors' notes" - names no listed skill and no listed domain, so the
structured signals all sit inactive and the ranking falls back to TF-IDF alone.

This module closes that gap using the standard **retrieve-then-rerank** pattern:

    stage 1  deterministic engine scores every open job          (fast, always works)
    stage 2  an LLM re-ranks and re-explains the top N of those  (smart, optional)

Stage 1 is the retrieval step and stage 2 is the precision step. Sending only
the top N to the model keeps the prompt small and the latency low, and means
the LLM never has to reason about the whole corpus.

Failure policy
--------------
This layer is strictly additive. Every failure mode - no API key, network down,
rate limit, malformed JSON, timeout, unknown job ids - returns None, and the
caller keeps the deterministic result. The feature can never make the product
worse than it is without it, which is what makes it safe to demo live.
"""

import json
import logging
from dataclasses import dataclass

from app.config import settings
from app.matching.parser import Intent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a hiring-search relevance judge.

You are given a candidate's free-text description of the role they want, the
structured signals a parser extracted from it, and a shortlist of job postings
that a keyword-and-heuristics engine already considered plausible.

Your job is to judge how well each posting actually serves what the candidate
described, and to say why in plain language.

Rules:
- Judge the WHOLE request, not just job titles. A posting whose title matches
  but whose domain, seniority, discipline or company type does not is a weak
  match, and must be scored accordingly.
- Reward postings that satisfy requirements the candidate stated but that do not
  appear in the job title (industry, company stage, work mode, seniority).
- Do not invent facts. Only use what appears in the posting text you are given.
- Write for the candidate, in second person.

Be SPECIFIC. Every explanation must name the actual company, industry, skills or
seniority from the posting - never generic praise.

The examples below use invented companies purely to show the required SHAPE.
Never reuse their wording or their details: describe only the postings you were
actually given.

  BAD:  "Strong match for skills and industry"
  BAD:  "This is a good fit for you"
  GOOD: "<Company> is the <industry> <company size> you described, and the role
         wants the <skill> and <skill> you asked for"
  GOOD: "Right stack and discipline, but <Company> is <industry>, not the
         <industry> you asked for, and it is <size> rather than a <size>"

Reply with ONLY a JSON object in exactly this shape, no prose around it:

{"results": [
  {"id": <the integer id given>,
   "relevance": <integer 0-100, where 100 is an ideal match and 0 is irrelevant>,
   "explanation": "<one specific sentence, 15-30 words, naming concrete details>",
   "reasons": ["<specific point naming a real attribute>", "<another>"]}
]}

Include every posting you were given, exactly once.

"reasons" must hold 2 to 4 entries, and EACH ONE MUST BE A FULL SENTENCE of
roughly 8 to 18 words. A bare label is not acceptable.

  BAD  reasons: ["Acme Corp", "Python", "Healthcare", "startup"]
  GOOD reasons: ["<Company> is a <size> <industry> company, matching both the
                  domain and the company size you asked for.",
                 "The role needs <skill> and <skill>, which is the stack you named.",
                 "You would also need <skill>, which you did not mention."]

At least one reason should be a gap or caveat where one genuinely exists - the
candidate is better served by knowing what they are missing.

Scores must spread across the range: an ideal match scores above 85, a
wrong-industry-but-right-skills match lands near 40, and a wrong-discipline
match lands below 30."""


@dataclass
class LlmVerdict:
    """One posting as judged by the model."""

    job_id: int
    relevance: float  # 0-100
    explanation: str
    reasons: list[str]


def is_available() -> bool:
    """True when an API key is configured. Does not check reachability."""
    return settings.llm_enabled


def model_name() -> str:
    return settings.groq_model


def _job_block(job, position: int) -> str:
    """Compact one posting for the prompt.

    The description is truncated deliberately: the model needs enough to judge
    relevance, not the whole advert, and a shorter prompt is a faster response.
    """
    skills = ", ".join(job.required_skills or []) or "none listed"
    description = " ".join((job.description or "").split())
    if len(description) > 320:
        description = description[:320].rsplit(" ", 1)[0] + "..."

    return (
        f"[{position}] {job.title}\n"
        f"    company: {job.company_name or 'unknown'} | industry: {job.domain or 'unspecified'} "
        f"| size: {job.company_stage} | location: {job.location} ({job.work_mode})\n"
        f"    seniority: {job.experience_level} | skills required: {skills}\n"
        f"    {description}"
    )


def _intent_summary(intent: Intent) -> str:
    parts = []
    if intent.skills:
        parts.append(f"skills={', '.join(intent.skills[:8])}")
    if intent.role_types:
        parts.append(f"discipline={', '.join(intent.role_types)}")
    if intent.domains:
        parts.append(f"industry={', '.join(intent.domains)}")
    if intent.locations:
        parts.append(f"location={', '.join(intent.locations)}")
    if intent.work_modes:
        parts.append(f"work mode={', '.join(intent.work_modes)}")
    if intent.company_stages:
        parts.append(f"company size={', '.join(intent.company_stages)}")
    if intent.experience_levels:
        parts.append(f"seniority={', '.join(intent.experience_levels)}")
    return "; ".join(parts) or "(the parser recognised nothing structured)"


def rerank(query: str, intent: Intent, scored_jobs: list) -> list[LlmVerdict] | None:
    """Re-rank and re-explain the shortlist. Returns None on any failure.

    `scored_jobs` are the top results from the deterministic engine, best first.
    """
    if not is_available() or not scored_jobs:
        return None

    shortlist = scored_jobs[: settings.llm_rerank_candidates]
    # Position in the prompt -> real job id, so the model only ever handles
    # small integers and we control the mapping back.
    by_position = {index + 1: item.job.id for index, item in enumerate(shortlist)}

    postings = "\n\n".join(_job_block(item.job, index + 1) for index, item in enumerate(shortlist))
    user_prompt = (
        f'Candidate wrote: "{query.strip()}"\n\n'
        f"Parser extracted: {_intent_summary(intent)}\n\n"
        f"Shortlisted postings:\n\n{postings}\n\n"
        f"Judge all {len(shortlist)} postings."
    )

    try:
        from groq import Groq  # imported lazily so the app runs without the package

        client = Groq(api_key=settings.groq_api_key, timeout=settings.groq_timeout_seconds)
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.2,  # low - this is a judging task, not a creative one
            max_tokens=1600,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        payload = json.loads(response.choices[0].message.content)
    except Exception as exc:  # noqa: BLE001 - any failure must degrade, never raise
        logger.warning("LLM re-rank unavailable, falling back to deterministic ranking: %s", exc)
        return None

    verdicts: list[LlmVerdict] = []
    for row in payload.get("results", []):
        try:
            job_id = by_position.get(int(row["id"]))
            if job_id is None:
                continue  # model invented an id - drop it rather than guess
            reasons = [str(r).strip() for r in (row.get("reasons") or []) if str(r).strip()]
            verdicts.append(
                LlmVerdict(
                    job_id=job_id,
                    relevance=max(0.0, min(100.0, float(row["relevance"]))),
                    explanation=str(row.get("explanation", "")).strip(),
                    reasons=reasons[:4],
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip the malformed row, keep the rest

    if not verdicts:
        logger.warning("LLM returned no usable verdicts; keeping deterministic ranking.")
        return None
    return verdicts
