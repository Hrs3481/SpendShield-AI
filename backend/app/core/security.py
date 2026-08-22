"""
Password hashing and JWT issuing/verification.

Two deliberate choices here:

* **bcrypt directly, not passlib.** passlib has been unmaintained since 2020 and
  crashes against bcrypt >= 4.1 while reading `bcrypt.__about__`.
* **PyJWT, not python-jose.** python-jose 3.3.0 carries known CVEs
  (CVE-2024-33663 algorithm confusion, CVE-2024-33664 JWT bomb) and is
  effectively unmaintained.

bcrypt silently truncates anything past 72 bytes, which would make
"<72 correct bytes> + anything" a valid password. We SHA-256 the password
first and hash the digest, so the full password always contributes.
"""
import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()


def _prehash(password: str) -> bytes:
    """SHA-256 -> base64 keeps every byte of the password inside bcrypt's 72-byte limit."""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash in the DB — treat as a failed login, never a 500.
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    """Returns the user id, or None if the token is invalid/expired/malformed."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],   # pinned list — never trust the header's alg
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
