"""Admin dashboard aggregates.

Everything is scoped to the calling admin's own job listings, so two admins
using the same instance never see each other's numbers.
"""

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import Application, ApplicationStatus, Job, JobStatus, User
from app.schemas import (
    ApplicationsPerJob,
    DashboardOut,
    PipelineCounts,
    SkillCount,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> DashboardOut:
    """Applications per job, skill distribution across applicants, pipeline counts."""
    jobs = list(db.scalars(select(Job).where(Job.created_by == admin.id)).all())
    job_ids = [job.id for job in jobs]

    applications: list[Application] = []
    if job_ids:
        applications = list(
            db.scalars(select(Application).where(Application.job_id.in_(job_ids))).all()
        )

    # --- pipeline totals ---------------------------------------------------
    status_counter = Counter(app.status for app in applications)
    pipeline = PipelineCounts(
        applied=status_counter.get(ApplicationStatus.APPLIED.value, 0),
        shortlisted=status_counter.get(ApplicationStatus.SHORTLISTED.value, 0),
        rejected=status_counter.get(ApplicationStatus.REJECTED.value, 0),
    )

    # --- per-job breakdown -------------------------------------------------
    by_job: dict[int, Counter] = {job.id: Counter() for job in jobs}
    for app in applications:
        by_job[app.job_id][app.status] += 1

    applications_per_job = [
        ApplicationsPerJob(
            job_id=job.id,
            job_title=job.title,
            status=JobStatus(job.status),
            total=sum(by_job[job.id].values()),
            applied=by_job[job.id].get(ApplicationStatus.APPLIED.value, 0),
            shortlisted=by_job[job.id].get(ApplicationStatus.SHORTLISTED.value, 0),
            rejected=by_job[job.id].get(ApplicationStatus.REJECTED.value, 0),
        )
        for job in jobs
    ]
    applications_per_job.sort(key=lambda row: row.total, reverse=True)

    # --- skill distribution across applicants ------------------------------
    # Read from the frozen profile_snapshot, not the live profile: the question
    # "what skills did our applicants have?" should not change retroactively
    # because someone edited their profile after applying.
    skill_counter: Counter[str] = Counter()
    for app in applications:
        snapshot_skills = (app.profile_snapshot or {}).get("skills") or []
        # Count each skill once per application, not once per mention.
        for skill in {str(s).strip() for s in snapshot_skills if str(s).strip()}:
            skill_counter[skill] += 1

    skill_distribution = [
        SkillCount(skill=skill, count=count) for skill, count in skill_counter.most_common(20)
    ]

    return DashboardOut(
        total_jobs=len(jobs),
        open_jobs=sum(1 for job in jobs if job.status == JobStatus.OPEN.value),
        closed_jobs=sum(1 for job in jobs if job.status == JobStatus.CLOSED.value),
        total_applications=len(applications),
        total_applicants=len({app.candidate_id for app in applications}),
        pipeline=pipeline,
        applications_per_job=applications_per_job,
        skill_distribution=skill_distribution,
    )
