"""Application endpoints - candidates apply, admins triage.

Pipeline: applied -> shortlisted -> rejected. Any transition between the three
is allowed (an admin can un-reject someone), but the status must be one of the
three known values; anything else is rejected by the Pydantic enum with a 422.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin, get_current_candidate
from app.models import (
    Application,
    ApplicationStatus,
    CandidateProfile,
    Job,
    JobStatus,
    User,
)
from app.schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationStatusUpdate,
    ApplicationWithCandidate,
    ApplicationWithJob,
    JobOut,
    MessageOut,
)

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def apply_to_job(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    candidate: User = Depends(get_current_candidate),
) -> ApplicationOut:
    """Apply to an open job, attaching a snapshot of the current profile."""
    job = db.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.status != JobStatus.OPEN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This listing is closed and is no longer accepting applications.",
        )

    duplicate = db.scalar(
        select(Application).where(
            Application.job_id == job.id, Application.candidate_id == candidate.id
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this job.",
        )

    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == candidate.id))
    if profile is None or not profile.skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete your profile (at least your skills) before applying.",
        )

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        status=ApplicationStatus.APPLIED.value,
        cover_note=(payload.cover_note or "").strip() or None,
        profile_snapshot=_snapshot(profile, candidate),
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return ApplicationOut.model_validate(application)


@router.get("/me", response_model=list[ApplicationWithJob])
def my_applications(
    db: Session = Depends(get_db),
    candidate: User = Depends(get_current_candidate),
) -> list[ApplicationWithJob]:
    """Everything the signed-in candidate has applied to, newest first."""
    applications = db.scalars(
        select(Application)
        .where(Application.candidate_id == candidate.id)
        .order_by(Application.created_at.desc())
    ).all()

    return [
        ApplicationWithJob(
            **ApplicationOut.model_validate(app).model_dump(),
            job=JobOut.model_validate(app.job),
        )
        for app in applications
    ]


@router.get("/job/{job_id}", response_model=list[ApplicationWithCandidate])
def applications_for_job(
    job_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
    status_filter: ApplicationStatus | None = Query(default=None, alias="status"),
) -> list[ApplicationWithCandidate]:
    """All applicants for one of the admin's own jobs."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.created_by != admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view applicants for job listings you created.",
        )

    stmt = select(Application).where(Application.job_id == job_id)
    if status_filter is not None:
        stmt = stmt.where(Application.status == status_filter.value)

    applications = db.scalars(stmt.order_by(Application.created_at.desc())).all()
    return [
        ApplicationWithCandidate(
            **ApplicationOut.model_validate(app).model_dump(),
            candidate_name=app.candidate.full_name,
            candidate_email=app.candidate.email,
        )
        for app in applications
    ]


@router.patch("/{application_id}/status", response_model=ApplicationOut)
def update_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> ApplicationOut:
    """Move an application through the hiring pipeline."""
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    if application.job.created_by != admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage applications for your own job listings.",
        )

    application.status = payload.status.value
    db.commit()
    db.refresh(application)
    return ApplicationOut.model_validate(application)


@router.delete("/{application_id}", response_model=MessageOut)
def withdraw(
    application_id: int,
    db: Session = Depends(get_db),
    candidate: User = Depends(get_current_candidate),
) -> MessageOut:
    """Let a candidate withdraw their own application."""
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    if application.candidate_id != candidate.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only withdraw your own applications.",
        )
    db.delete(application)
    db.commit()
    return MessageOut(detail="Application withdrawn.")


def _snapshot(profile: CandidateProfile, user: User) -> dict:
    """Freeze the profile fields an admin needs to review an application."""
    return {
        "full_name": profile.full_name,
        "email": user.email,
        "headline": profile.headline,
        "skills": profile.skills or [],
        "education": profile.education or [],
        "projects": profile.projects or [],
        "years_experience": profile.years_experience,
        "preferred_location": profile.preferred_location,
        "preferred_role_type": profile.preferred_role_type,
        "domain_interests": profile.domain_interests or [],
        "work_mode_preference": profile.work_mode_preference,
    }
