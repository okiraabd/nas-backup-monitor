"""Authentication service — verify credentials and issue tokens."""
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.security import create_access_token, verify_password


class AuthError(Exception):
    """Raised on authentication failure. `status_code` maps to HTTP response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def authenticate(db: Session, username: str, password: str) -> tuple[User, str]:
    """Validate credentials and return (user, access_token).

    Raises AuthError(401) on bad username/password, AuthError(403) on inactive user.
    """
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError(401, "Invalid username or password")
    if not user.is_active:
        raise AuthError(403, "User is inactive")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token, _claims = create_access_token(
        subject=user.username,
        role=user.role,
        user_id=user.id,
        token_version=user.token_version,
    )
    return user, token


def refresh_access_token(db: Session, payload: dict) -> tuple[User, str]:
    """Issue a fresh token and revoke the presented one (token rotation).

    The caller must present a currently-valid token (already verified by the
    dependency). We revoke its `jti` so it cannot be reused, then mint a new
    token. This shortens the useful life of any single leaked token.

    Raises AuthError(401) if the user no longer exists, AuthError(403) if inactive.
    """
    user = db.get(User, payload.get("uid"))
    if user is None:
        raise AuthError(401, "User not found")
    if not user.is_active:
        raise AuthError(403, "User is inactive")

    # Rotate: revoke the old token, then issue a new one.
    revoke_token(db, payload)
    token, _claims = create_access_token(
        subject=user.username,
        role=user.role,
        user_id=user.id,
        token_version=user.token_version,
    )
    return user, token


def revoke_token(db: Session, payload: dict) -> None:
    """Add a token's jti to the denylist so it's rejected immediately (logout).

    Also opportunistically purges denylist rows whose tokens have already
    expired, keeping the table small without a separate cron job.
    """
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti is None or exp is None:
        return  # nothing to revoke (older token shape); treat as no-op

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

    # Lazy cleanup of already-expired denylist entries.
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc)))

    if db.get(RevokedToken, jti) is None:
        db.add(
            RevokedToken(
                jti=jti,
                user_id=payload.get("uid"),
                expires_at=expires_at,
            )
        )
    db.commit()
