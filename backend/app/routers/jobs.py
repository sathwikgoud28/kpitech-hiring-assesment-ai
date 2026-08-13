"""Job listing endpoints.

Reads are public (a candidate browses before signing in); writes require a
Company Admin, and an admin may only edit or delete jobs they created.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import ExperienceLevel, Job, JobStatus, User, WorkMode
from app.schemas import JobCreate, JobListOut, JobOut, JobUpdate, MessageOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=JobListOut)
def list_jobs(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, description="Free-text search over title, description, company."),
    skills: str | None = Query(default=None, description="Comma-separated skills; a job matches if it requires ANY of them."),
    location: str | None = Query(default=None),
    experience_level: ExperienceLevel | None = Query(default=None),
    work_mode: WorkMode | None = Query(default=None),
    domain: str | None = Query(default=None),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    mine: bool = Query(default=False, description="Ignored unless combined with an admin token upstream."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobListOut:
    """Search and filter job listings.

    Skill filtering is done in Python rather than SQL because `required_skills`
    is a JSON column - SQLite cannot index inside it. At this dataset size the
    cost is negligible; the fix at scale is a normalised job_skills table.
    """
    stmt = select(Job)

    if status_filter is not None:
        stmt = stmt.where(Job.status == status_filter.value)
    if experience_level is not None:
        stmt = stmt.where(Job.experience_level == experience_level.value)
    if work_mode is not None:
        stmt = stmt.where(Job.work_mode == work_mode.value)
    if location:
        stmt = stmt.where(func.lower(Job.location).contains(location.strip().lower()))
    if domain:
        stmt = stmt.where(func.lower(Job.domain).contains(domain.strip().lower()))
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Job.title).like(needle),
                func.lower(Job.description).like(needle),
                func.lower(Job.company_name).like(needle),
            )
        )

    jobs = list(db.scalars(stmt.order_by(Job.created_at.desc())).all())

    if skills:
        wanted = {s.strip().lower() for s in skills.split(",") if s.strip()}
        if wanted:
            jobs = [
                job
                for job in jobs
                if wanted & {s.lower() for s in (job.required_skills or [])}
            ]

    total = len(jobs)
    page = jobs[offset : offset + limit]
    return JobListOut(total=total, items=[JobOut.model_validate(job) for job in page])


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return JobOut.model_validate(job)


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> JobOut:
    job = Job(
        **payload.model_dump(mode="json"),
        created_by=admin.id,
    )
    # Fall back to the admin's own company if they left the field blank.
    if not job.company_name:
        job.company_name = admin.company_name or ""
    db.add(job)
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@router.put("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> JobOut:
    job = _get_own_job(db, job_id, admin)
    for field, value in payload.model_dump(mode="json", exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@router.patch("/{job_id}/status", response_model=JobOut)
def set_job_status(
    job_id: int,
    new_status: JobStatus,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> JobOut:
    """Convenience toggle so the UI can open/close a listing in one click."""
    job = _get_own_job(db, job_id, admin)
    job.status = new_status.value
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@router.delete("/{job_id}", response_model=MessageOut)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> MessageOut:
    job = _get_own_job(db, job_id, admin)
    db.delete(job)  # cascade removes this job's applications
    db.commit()
    return MessageOut(detail="Job deleted.")


def _get_own_job(db: Session, job_id: int, admin: User) -> Job:
    """Load a job and assert the calling admin owns it."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.created_by != admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage job listings you created.",
        )
    return job
