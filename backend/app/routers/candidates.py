"""Candidate profile endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin, get_current_candidate
from app.models import CandidateProfile, User
from app.schemas import ProfileOut, ProfileUpsert

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("/me/profile", response_model=ProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    candidate: User = Depends(get_current_candidate),
) -> ProfileOut:
    profile = _load_or_create(db, candidate)
    return ProfileOut.model_validate(profile)


@router.put("/me/profile", response_model=ProfileOut)
def upsert_my_profile(
    payload: ProfileUpsert,
    db: Session = Depends(get_db),
    candidate: User = Depends(get_current_candidate),
) -> ProfileOut:
    """Create or replace the signed-in candidate's profile.

    Uses PUT because the body is the complete profile, not a partial patch -
    sending it twice produces the same result.
    """
    profile = _load_or_create(db, candidate)

    profile.full_name = payload.full_name.strip()
    profile.headline = (payload.headline or "").strip() or None
    profile.skills = payload.skills
    profile.education = [item.model_dump() for item in payload.education]
    profile.projects = [item.model_dump() for item in payload.projects]
    profile.years_experience = payload.years_experience
    profile.preferred_location = (payload.preferred_location or "").strip() or None
    profile.preferred_role_type = (payload.preferred_role_type or "").strip() or None
    profile.domain_interests = payload.domain_interests
    profile.work_mode_preference = (
        payload.work_mode_preference.value if payload.work_mode_preference else None
    )

    # Keep the account's display name in step with the profile name.
    candidate.full_name = profile.full_name

    db.commit()
    db.refresh(profile)
    return ProfileOut.model_validate(profile)


@router.get("/{candidate_id}/profile", response_model=ProfileOut)
def get_candidate_profile(
    candidate_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> ProfileOut:
    """Admin-only view of an applicant's current profile."""
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == candidate_id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found."
        )
    return ProfileOut.model_validate(profile)


def _load_or_create(db: Session, candidate: User) -> CandidateProfile:
    """Return the candidate's profile, creating an empty one if missing.

    Registration already creates a profile row, so this only fires for accounts
    created before that behaviour existed (or seeded directly).
    """
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == candidate.id))
    if profile is None:
        profile = CandidateProfile(user_id=candidate.id, full_name=candidate.full_name)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile
