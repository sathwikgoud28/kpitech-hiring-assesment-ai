"""Pydantic request/response models.

These are the API contract. Keeping them separate from the ORM models means the
database can change shape without silently changing what clients receive.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import (
    ApplicationStatus,
    CompanyStage,
    ExperienceLevel,
    JobStatus,
    UserRole,
    WorkMode,
)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    role: UserRole
    company_name: str | None = Field(default=None, max_length=160)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    company_name: str | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --------------------------------------------------------------------------- #
# Candidate profile
# --------------------------------------------------------------------------- #
class EducationItem(BaseModel):
    degree: str = Field(min_length=1, max_length=160)
    institution: str = Field(default="", max_length=160)
    year: str = Field(default="", max_length=20)


class ProjectItem(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(default="", max_length=2000)
    tech: list[str] = Field(default_factory=list)


class ProfileUpsert(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    headline: str | None = Field(default=None, max_length=200)
    skills: list[str] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    years_experience: float = Field(default=0.0, ge=0, le=60)
    preferred_location: str | None = Field(default=None, max_length=120)
    preferred_role_type: str | None = Field(default=None, max_length=120)
    domain_interests: list[str] = Field(default_factory=list)
    work_mode_preference: WorkMode | None = None

    @field_validator("skills", "domain_interests")
    @classmethod
    def clean_list(cls, values: list[str]) -> list[str]:
        """Trim, drop blanks and de-duplicate case-insensitively."""
        seen: dict[str, str] = {}
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned.lower() not in seen:
                seen[cleaned.lower()] = cleaned
        return list(seen.values())


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    full_name: str
    headline: str | None
    skills: list[str]
    education: list[EducationItem]
    projects: list[ProjectItem]
    years_experience: float
    preferred_location: str | None
    preferred_role_type: str | None
    domain_interests: list[str]
    work_mode_preference: str | None
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #
class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1)
    required_skills: list[str] = Field(default_factory=list)
    experience_level: ExperienceLevel
    location: str = Field(min_length=1, max_length=120)
    status: JobStatus = JobStatus.OPEN
    company_name: str = Field(default="", max_length=160)
    domain: str = Field(default="", max_length=80)
    work_mode: WorkMode = WorkMode.ONSITE
    company_stage: CompanyStage = CompanyStage.MIDSIZE
    min_years_experience: float = Field(default=0.0, ge=0, le=40)

    @field_validator("required_skills")
    @classmethod
    def clean_skills(cls, values: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned.lower() not in seen:
                seen[cleaned.lower()] = cleaned
        return list(seen.values())


class JobUpdate(BaseModel):
    """Every field optional - this backs a PATCH-style partial update."""

    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, min_length=1)
    required_skills: list[str] | None = None
    experience_level: ExperienceLevel | None = None
    location: str | None = Field(default=None, min_length=1, max_length=120)
    status: JobStatus | None = None
    company_name: str | None = Field(default=None, max_length=160)
    domain: str | None = Field(default=None, max_length=80)
    work_mode: WorkMode | None = None
    company_stage: CompanyStage | None = None
    min_years_experience: float | None = Field(default=None, ge=0, le=40)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    required_skills: list[str]
    experience_level: ExperienceLevel
    location: str
    status: JobStatus
    company_name: str
    domain: str
    work_mode: WorkMode
    company_stage: CompanyStage
    min_years_experience: float
    created_by: int
    created_at: datetime
    updated_at: datetime


class JobListOut(BaseModel):
    total: int
    items: list[JobOut]


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #
class ApplicationCreate(BaseModel):
    job_id: int
    cover_note: str | None = Field(default=None, max_length=2000)


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    candidate_id: int
    status: ApplicationStatus
    cover_note: str | None
    profile_snapshot: dict
    created_at: datetime
    updated_at: datetime


class ApplicationWithJob(ApplicationOut):
    job: JobOut


class ApplicationWithCandidate(ApplicationOut):
    candidate_name: str
    candidate_email: EmailStr


# --------------------------------------------------------------------------- #
# AI matching
# --------------------------------------------------------------------------- #
class MatchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    limit: int = Field(default=10, ge=1, le=50)
    # When true and the caller is a signed-in candidate, their saved profile is
    # blended into the query so results reflect skills they did not retype.
    use_profile: bool = True
    # When true and an API key is configured, the top deterministic results are
    # re-ranked and re-explained by an LLM. Falls back silently if unavailable.
    use_llm: bool = True


class ScoreBreakdown(BaseModel):
    semantic: float
    skills: float
    role_type: float
    domain: float
    location: float
    experience: float
    company_stage: float


class MatchResult(BaseModel):
    job: JobOut
    score: float = Field(description="Overall match quality, 0-100.")
    explanation: str
    reasons: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    breakdown: ScoreBreakdown
    # Populated only when the LLM layer ran and judged this particular result.
    engine_score: float | None = Field(
        default=None, description="The deterministic score before LLM blending."
    )
    llm_relevance: float | None = Field(
        default=None, description="The LLM's own 0-100 relevance judgement."
    )


class ParsedIntent(BaseModel):
    """What the parser understood from the free-text query - shown in the UI so
    the behaviour is inspectable rather than a black box."""

    skills: list[str]
    domains: list[str]
    locations: list[str]
    role_types: list[str]
    work_modes: list[str]
    company_stages: list[str]
    experience_levels: list[str]


class MatchResponse(BaseModel):
    query: str
    parsed: ParsedIntent
    used_profile: bool
    total_open_jobs: int
    results: list[MatchResult]
    # How the results were ranked, so the UI can be honest about which path ran.
    llm_used: bool = False
    llm_model: str | None = None
    llm_available: bool = False


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class ApplicationsPerJob(BaseModel):
    job_id: int
    job_title: str
    status: JobStatus
    total: int
    applied: int
    shortlisted: int
    rejected: int


class SkillCount(BaseModel):
    skill: str
    count: int


class PipelineCounts(BaseModel):
    applied: int
    shortlisted: int
    rejected: int


class DashboardOut(BaseModel):
    total_jobs: int
    open_jobs: int
    closed_jobs: int
    total_applications: int
    total_applicants: int
    pipeline: PipelineCounts
    applications_per_job: list[ApplicationsPerJob]
    skill_distribution: list[SkillCount]


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #
class MessageOut(BaseModel):
    detail: str
