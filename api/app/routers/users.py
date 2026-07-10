"""User management router. All endpoints are admin-only (RBAC)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import ROLE_ADMIN, ROLE_COLLECTOR, ROLE_SERVICE, User
from app.schemas.user import (
    PasswordUpdate,
    RotateTokenResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import generate_password, hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _active_admin_count(db: Session) -> int:
    """Count active admin users; used to prevent accidental admin lockout."""
    return db.scalar(
        select(func.count()).select_from(User).where(
            User.role == ROLE_ADMIN,
            User.is_active.is_(True),
        )
    ) or 0


def _ensure_admin_access_can_be_removed(db: Session, user: User) -> None:
    """Reject operations that would leave the system with no active admin."""
    if user.role == ROLE_ADMIN and user.is_active and _active_admin_count(db) <= 1:
        raise HTTPException(
            status_code=400,
            detail="At least one active admin must remain",
        )


@router.get(
    "",
    response_model=list[UserOut],
    summary="List users",
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[User]:
    """List all users. Role: admin."""
    return db.scalars(select(User).order_by(User.id)).all()


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    """Create a user. Role: admin."""
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Get a user",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    """Get a single user. Role: admin."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Update a user",
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    """Update a user's display_name/role/is_active. Role: admin."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    would_remove_own_admin = (
        user.id == current_user.id
        and user.role == ROLE_ADMIN
        and (
            (payload.role is not None and payload.role != ROLE_ADMIN)
            or payload.is_active is False
        )
    )
    if would_remove_own_admin:
        raise HTTPException(
            status_code=400,
            detail="You cannot remove your own admin access",
        )

    would_remove_active_admin = (
        user.role == ROLE_ADMIN
        and user.is_active
        and (
            (payload.role is not None and payload.role != ROLE_ADMIN)
            or payload.is_active is False
        )
    )
    if would_remove_active_admin:
        _ensure_admin_access_can_be_removed(db, user)

    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        # Reactivating or deactivating; deactivation also invalidates tokens.
        if user.is_active and not payload.is_active:
            user.token_version += 1
        user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a user",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    """Soft delete: set is_active=false. Role: admin."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot disable your own account")
    _ensure_admin_access_can_be_removed(db, user)
    user.is_active = False
    user.token_version += 1  # invalidate any existing tokens
    db.commit()


@router.patch(
    "/{user_id}/password",
    response_model=UserOut,
    summary="Reset a user's password",
)
def reset_password(
    user_id: int,
    payload: PasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> User:
    """Admin resets another user's password. Role: admin.

    Bumps token_version so all existing tokens for that user are invalidated.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/{user_id}/rotate-token",
    response_model=RotateTokenResponse,
    summary="Rotate a machine account password",
)
def rotate_token(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> RotateTokenResponse:
    """Generate a new password for a service/collector account (shown once).

    Only applicable to machine accounts (service/collector). Bumps token_version
    to invalidate old tokens. Role: admin.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role not in {ROLE_SERVICE, ROLE_COLLECTOR}:
        raise HTTPException(
            status_code=400,
            detail="Token rotation is only for service/collector accounts",
        )
    new_password = generate_password()
    user.password_hash = hash_password(new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return RotateTokenResponse(
        user_id=user.id, username=user.username, new_password=new_password
    )
