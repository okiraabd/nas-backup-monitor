"""Password hashing and JWT token helpers."""
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt.exceptions import PyJWTError

from app.config import settings


def generate_password(length: int = 20) -> str:
    """Generate a cryptographically strong random password (for token rotation)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# --- Password hashing (bcrypt) ---
def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT ---
def create_access_token(
    subject: str, role: str, user_id: int, token_version: int = 0
) -> tuple[str, dict]:
    """Create a signed JWT for the given user.

    Returns (token, claims). The claims include:
      - jti: unique token id, used for the revocation denylist
      - tv:  the user's token_version, used for bulk "logout everywhere"
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,       # username
        "uid": user_id,
        "role": role,
        "tv": token_version,
        "jti": uuid.uuid4().hex,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": expire,
        "iat": now,
        "nbf": now,           # not-valid-before = now
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, payload


def decode_access_token(token: str) -> dict | None:
    """Decode and fully validate a JWT.

    Verifies signature, expiry (exp), not-before (nbf), issuer (iss) and
    audience (aud). Returns the claims dict, or None if any check fails.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except PyJWTError:
        return None
