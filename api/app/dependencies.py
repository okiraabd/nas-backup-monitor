"""Auth dependencies: extract current user from JWT and enforce roles (RBAC)."""
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.security import decode_access_token

# HTTPBearer produces the "Authorize" button in Swagger and reads the
# Authorization: Bearer <token> header.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Bearer token, or 401."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revocation check 1: this specific token was logged out (JTI denylist).
    jti = payload.get("jti")
    if jti is not None and db.get(RevokedToken, jti) is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("uid")
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive"
        )

    # Revocation check 2: all of this user's tokens were invalidated in bulk
    # (e.g. password reset / token rotation bumped token_version).
    if payload.get("tv", 0) != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated, please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Return the decoded JWT claims (for handlers that need jti/exp, e.g. logout)."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def require_roles(*roles: str) -> Callable[[User], User]:
    """Dependency factory: allow only users whose role is in `roles`."""

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted for this action",
            )
        return current_user

    return checker


# Convenience dependencies
require_admin = require_roles("admin")
require_service = require_roles("service")
require_collector = require_roles("collector")
require_operator_or_admin = require_roles("admin", "operator")
