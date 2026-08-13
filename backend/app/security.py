"""Password hashing and JWT issuing/verification.

Passwords use PBKDF2-HMAC-SHA256 from the standard library with a per-user
random salt and 260,000 iterations. This avoids the bcrypt/passlib version
conflicts that are common on Windows while still being a correct, salted,
slow KDF. A production system would use Argon2id.
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

_ITERATIONS = 260_000
_ALGO = "sha256"


def hash_password(password: str) -> tuple[str, str]:
    """Return (hex_hash, hex_salt) for a plaintext password."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, stored_salt: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    try:
        salt = bytes.fromhex(stored_salt)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _ITERATIONS)
    return hmac.compare_digest(digest.hex(), stored_hash)


def create_access_token(subject: str, role: str) -> str:
    """Issue a signed JWT carrying the user id and role."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(subject), "role": role, "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    """Return the token payload, or None if it is invalid or expired."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        return None
