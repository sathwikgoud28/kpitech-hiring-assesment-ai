"""SQLAlchemy ORM models.

Design notes
------------
* List-shaped attributes (skills, education, projects, domain interests) are
  stored as JSON columns. For a job board of this size that keeps the schema
  small and readable; a production system would normalise `skills` into its own
  table so it could be indexed and deduplicated globally.
* `Application.profile_snapshot` freezes the candidate's profile at the moment
  they applied. The brief says "application includes the candidate's profile
  details" - snapshotting means an admin reviewing an old application sees what
  was actually submitted, not whatever the candidate edited later.
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    ADMIN = "admin"
    CANDIDATE = "candidate"


class JobStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class ExperienceLevel(str, Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"


class WorkMode(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"


class CompanyStage(str, Enum):
    STARTUP = "startup"
    MIDSIZE = "midsize"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Only meaningful for admins - the company they post jobs on behalf of.
    company_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    profile: Mapped["CandidateProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="owner")
    applications: Mapped[list["Application"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    headline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    # [{"degree": "...", "institution": "...", "year": "..."}]
    education: Mapped[list] = mapped_column(JSON, default=list)
    # [{"title": "...", "summary": "...", "tech": ["..."]}]
    projects: Mapped[list] = mapped_column(JSON, default=list)
    years_experience: Mapped[float] = mapped_column(default=0.0)

    # Preferences - these feed the AI matcher when a candidate opts in.
    preferred_location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_role_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    domain_interests: Mapped[list] = mapped_column(JSON, default=list)
    work_mode_preference: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    experience_level: Mapped[str] = mapped_column(String(20), nullable=False)
    location: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.OPEN.value, index=True)

    # Extra fields beyond the minimum brief. They exist because the example query
    # -- "a Python backend role in a startup that does healthcare" -- names a
    # domain and a company stage. Without these columns the matcher would have to
    # guess both from free text.
    company_name: Mapped[str] = mapped_column(String(160), default="")
    domain: Mapped[str] = mapped_column(String(80), default="")
    work_mode: Mapped[str] = mapped_column(String(20), default=WorkMode.ONSITE.value)
    company_stage: Mapped[str] = mapped_column(String(20), default=CompanyStage.MIDSIZE.value)
    min_years_experience: Mapped[float] = mapped_column(default=0.0)

    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(back_populates="jobs")
    applications: Mapped[list["Application"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Application(Base):
    __tablename__ = "applications"
    # A candidate may only apply to a given job once.
    __table_args__ = (UniqueConstraint("job_id", "candidate_id", name="uq_job_candidate"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ApplicationStatus.APPLIED.value, index=True
    )
    cover_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Frozen copy of the candidate profile as submitted.
    profile_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    job: Mapped[Job] = relationship(back_populates="applications")
    candidate: Mapped[User] = relationship(back_populates="applications")
