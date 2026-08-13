"""Turn a natural-language job wish into structured intent.

Example
-------
    "I want a Python backend role in a startup that does healthcare"

becomes

    Intent(
        skills=["Python"],
        role_types=["Backend"],
        company_stages=["startup"],
        domains=["Healthcare"],
        ...
    )

The approach is alias matching against the taxonomy plus a few regexes for
numeric experience. It is not a neural model, and that is a deliberate
trade-off I can defend: it is deterministic, instant, needs no API key or
network, and every decision it makes is traceable to one line in taxonomy.py.
The cost is that it only understands vocabulary I have taught it - a genuinely
novel phrasing falls through to the TF-IDF layer, which is exactly what that
layer is there for.
"""

import re
from dataclasses import dataclass, field

from app.matching.taxonomy import (
    COMPANY_STAGE_LOOKUP,
    DOMAIN_LOOKUP,
    EXPERIENCE_LEVEL_LOOKUP,
    LOCATION_LOOKUP,
    ROLE_TYPE_LOOKUP,
    SKILL_LOOKUP,
    WORK_MODE_LOOKUP,
)
from app.matching.text import normalize

# "5 years", "3+ yrs", "2 to 4 years"
_YEARS_RE = re.compile(r"(\d{1,2})\s*(?:\+|-|to|–)?\s*(?:\d{1,2})?\s*(?:\+)?\s*(?:years?|yrs?)")


@dataclass
class Intent:
    """Everything the parser managed to pull out of the query."""

    raw_query: str
    skills: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    role_types: list[str] = field(default_factory=list)
    work_modes: list[str] = field(default_factory=list)
    company_stages: list[str] = field(default_factory=list)
    experience_levels: list[str] = field(default_factory=list)
    years_experience: float | None = None

    def is_empty(self) -> bool:
        """True when nothing structured was recognised at all."""
        return not any(
            [
                self.skills,
                self.domains,
                self.locations,
                self.role_types,
                self.work_modes,
                self.company_stages,
                self.experience_levels,
            ]
        )


def _find_all(text: str, lookup: list[tuple[str, str]], limit: int | None = None) -> list[str]:
    """Collect canonical labels whose alias appears in `text`.

    Aliases arrive longest-first, so once "react native" matches we blank it out
    of the working copy and the bare "react" alias can no longer fire on the
    same span. That is what stops one phrase producing two contradictory hits.
    """
    working = f" {text} "
    found: list[str] = []
    for surface, canonical in lookup:
        if canonical in found:
            continue
        # Word-boundary-ish check that still works for tokens like "c#" and ".net",
        # which `\b` handles badly because # and . are not word characters.
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(surface)}(?![a-z0-9])")
        if pattern.search(working):
            found.append(canonical)
            working = pattern.sub(" ", working)
            if limit is not None and len(found) >= limit:
                break
    return found


def parse_query(query: str) -> Intent:
    """Parse a free-text query into an Intent."""
    text = normalize(query)
    intent = Intent(raw_query=query)

    # Order matters: pull the most specific vocabularies out first so their
    # words are consumed before a broader vocabulary can claim them.
    intent.skills = _find_all(text, SKILL_LOOKUP, limit=12)
    intent.role_types = _find_all(text, ROLE_TYPE_LOOKUP, limit=4)
    intent.domains = _find_all(text, DOMAIN_LOOKUP, limit=4)
    intent.locations = _find_all(text, LOCATION_LOOKUP, limit=4)
    intent.work_modes = _find_all(text, WORK_MODE_LOOKUP, limit=2)
    intent.company_stages = _find_all(text, COMPANY_STAGE_LOOKUP, limit=2)
    intent.experience_levels = _find_all(text, EXPERIENCE_LEVEL_LOOKUP, limit=2)

    # "Remote" is both a location and a work mode; treat it as both so a query
    # of just "remote python job" filters correctly either way.
    if "Remote" in intent.locations and "remote" not in intent.work_modes:
        intent.work_modes.append("remote")

    match = _YEARS_RE.search(text)
    if match:
        intent.years_experience = float(match.group(1))
        # A bare number beats a vague word: "3 years" implies mid-level even if
        # the sentence also contains "senior".
        if not intent.experience_levels:
            intent.experience_levels = [_level_for_years(intent.years_experience)]

    return intent


def _level_for_years(years: float) -> str:
    if years < 2:
        return "entry"
    if years < 5:
        return "mid"
    if years < 8:
        return "senior"
    return "lead"


def enrich_with_profile(intent: Intent, profile) -> Intent:
    """Fold a candidate's saved profile into the parsed intent.

    The query stays primary - profile values only fill gaps the query left
    empty, and profile skills are appended rather than replacing typed ones.
    This means typing "I want a frontend role" while having a backend-heavy
    profile still returns frontend jobs.
    """
    if profile is None:
        return intent

    for skill in profile.skills or []:
        if skill not in intent.skills:
            intent.skills.append(skill)

    if not intent.domains:
        intent.domains = list(profile.domain_interests or [])

    if not intent.locations and profile.preferred_location:
        intent.locations = _find_all(normalize(profile.preferred_location), LOCATION_LOOKUP, limit=2) or [
            profile.preferred_location
        ]

    if not intent.role_types and profile.preferred_role_type:
        intent.role_types = _find_all(normalize(profile.preferred_role_type), ROLE_TYPE_LOOKUP, limit=2)

    if not intent.work_modes and profile.work_mode_preference:
        intent.work_modes = [profile.work_mode_preference]

    if intent.years_experience is None and profile.years_experience:
        intent.years_experience = float(profile.years_experience)
        if not intent.experience_levels:
            intent.experience_levels = [_level_for_years(intent.years_experience)]

    return intent
