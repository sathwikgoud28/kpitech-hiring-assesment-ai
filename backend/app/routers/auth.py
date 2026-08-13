"""Registration, login and 'who am I' endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import CandidateProfile, User, UserRole
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Create an account and return a token, so the UI can sign the user
    straight in rather than bouncing them to a second login screen."""
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    password_hash, salt = hash_password(payload.password)
    user = User(
        email=payload.email.lower(),
        password_hash=password_hash,
        password_salt=salt,
        role=payload.role.value,
        full_name=payload.full_name.strip(),
        company_name=(payload.company_name or "").strip() or None,
    )
    db.add(user)
    db.flush()  # assign user.id without committing yet

    # Candidates get an empty profile immediately so the frontend never has to
    # handle a "profile does not exist yet" branch.
    if user.role == UserRole.CANDIDATE.value:
        db.add(CandidateProfile(user_id=user.id, full_name=user.full_name))

    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    # Same message for "no such user" and "wrong password" so the endpoint
    # cannot be used to enumerate registered emails.
    if user is None or not verify_password(payload.password, user.password_hash, user.password_salt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    token = create_access_token(subject=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
