"""User management router. All endpoints are admin-only (RBAC)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.backup_log import BackupLog
from app.models.metric import Metric
from app.models.report import Report
from app.models.user import ROLE_ADMIN, ROLE_COLLECTOR, ROLE_SERVICE, User
from app.schemas.user import (
    GeneratedPasswordResponse,
    PasswordUpdate,
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


def _user_has_related_data(db: Session, user_id: int) -> dict:
    """Check if a user has related data in logs, metrics, or reports."""
    log_count = db.scalar(
        select(func.count()).select_from(BackupLog).where(
            (BackupLog.reported_by == user_id) | (BackupLog.acknowledged_by == user_id)
        )
    ) or 0
    metric_count = db.scalar(
        select(func.count()).select_from(Metric).where(Metric.collected_by == user_id)
    ) or 0
    report_count = db.scalar(
        select(func.count()).select_from(Report).where(Report.generated_by == user_id)
    ) or 0
    return {
        "has_data": (log_count + metric_count + report_count) > 0,
        "log_count": log_count,
        "metric_count": metric_count,
        "report_count": report_count,
    }


@router.get(
    "",
    response_model=list[UserOut],
    summary="List users",
)
def list_users(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
    include_inactive: bool = Query(False, description="Include inactive/disabled users"),
) -> list[User]:
    """List all users. Role: admin."""
    # Default view hides disabled accounts; admins can opt into the full list.
    q = select(User).order_by(User.id)
    if not include_inactive:
        q = q.where(User.is_active.is_(True))
    return db.scalars(q).all()


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
    # Username is immutable after creation, so reject duplicates up front.
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
    _current_user: User = Depends(require_admin),
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

    # Prevent an admin from locking themselves or the system out of admin access.
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
    summary="Delete a user (smart: hard if no data, soft otherwise)",
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    force: bool = Query(
        False,
        description="If true, hard-delete even when user has related data (sets FK to NULL).",
    ),
) -> None:
    """Smart delete: hard delete if no related data, soft delete otherwise.

    With force=true, an admin can hard-delete a user that has related data;
    FK columns (reported_by, acknowledged_by, collected_by, generated_by) are
    set to NULL on the related rows before the user row is removed.
    Role: admin.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    _ensure_admin_access_can_be_removed(db, user)

    relation = _user_has_related_data(db, user_id)

    # Preserve historical ownership by soft-deleting users that are referenced,
    # unless the caller explicitly asks to detach those rows with force=true.
    if not relation["has_data"] or force:
        if relation["has_data"]:
            # Nullify FK references before hard delete
            db.execute(
                BackupLog.__table__.update()
                .where(BackupLog.reported_by == user_id)
                .values(reported_by=None)
            )
            db.execute(
                BackupLog.__table__.update()
                .where(BackupLog.acknowledged_by == user_id)
                .values(acknowledged_by=None)
            )
            db.execute(
                Metric.__table__.update()
                .where(Metric.collected_by == user_id)
                .values(collected_by=None)
            )
            db.execute(
                Report.__table__.update()
                .where(Report.generated_by == user_id)
                .values(generated_by=None)
            )
        db.delete(user)
        db.commit()
    else:
        # Soft delete: deactivate and invalidate tokens
        user.is_active = False
        user.token_version += 1
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
    _current_user: User = Depends(require_admin),
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
    "/{user_id}/password/generate",
    response_model=GeneratedPasswordResponse,
    summary="Generate a random account password",
)
def generate_random_password(
    user_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
) -> GeneratedPasswordResponse:
    """Generate a new password for an account (shown once).

    Bumps token_version to invalidate old tokens. Role: admin.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Plaintext is returned once; only the bcrypt hash is stored.
    new_password = generate_password()
    user.password_hash = hash_password(new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return GeneratedPasswordResponse(
        user_id=user.id, username=user.username, new_password=new_password
    )
