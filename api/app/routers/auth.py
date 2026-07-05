"""Auth router: login, logout, me."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_token_payload
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    UserPublic,
)
from app.services.auth_service import (
    AuthError,
    authenticate,
    refresh_access_token,
    revoke_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Exchange username/password for a JWT access token."""
    try:
        user, token = authenticate(db, payload.username, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return LoginResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post("/logout", response_model=MessageResponse)
def logout(
    payload: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Log out by revoking the current token.

    The token's `jti` is added to the server-side denylist, so this exact token
    is rejected on every subsequent request even before it expires. The client
    should also discard the token from localStorage.
    """
    revoke_token(db, payload)
    return MessageResponse(message="Logged out. Token has been revoked.")


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    """Return the currently authenticated user's profile."""
    return UserPublic.model_validate(current_user)


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    current_user: User = Depends(get_current_user),
    payload: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Rotate the current token for a fresh one.

    `get_current_user` enforces that the presented token is still fully valid
    (not revoked, not invalidated, user active) before we rotate it. The old
    token is revoked and a new short-lived token is returned. This lets clients
    keep a short access-token lifetime while staying logged in.
    """
    try:
        user, token = refresh_access_token(db, payload)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return LoginResponse(access_token=token, user=UserPublic.model_validate(user))
