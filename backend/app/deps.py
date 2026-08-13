"""Shared FastAPI dependencies: current user resolution and role guards."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated or token is invalid/expired.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the User behind the Bearer token, or raise 401."""
    if credentials is None:
        raise CREDENTIALS_ERROR

    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise CREDENTIALS_ERROR

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise CREDENTIALS_ERROR
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Allow only company admins through."""
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a Company Admin account.",
        )
    return user


def get_current_candidate(user: User = Depends(get_current_user)) -> User:
    """Allow only candidates through."""
    if user.role != UserRole.CANDIDATE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a Candidate account.",
        )
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of raising.

    Used by endpoints that work anonymously but get richer when signed in -
    e.g. AI matching can blend in the candidate's saved profile.
    """
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        return None
    return db.get(User, int(payload["sub"]))
