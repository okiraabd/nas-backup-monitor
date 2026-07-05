"""User model — auth accounts with role-based access."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Valid roles for the system.
ROLE_ADMIN = "admin"
ROLE_SERVICE = "service"
ROLE_COLLECTOR = "collector"
ROLE_OPERATOR = "operator"
VALID_ROLES = {ROLE_ADMIN, ROLE_SERVICE, ROLE_COLLECTOR, ROLE_OPERATOR}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Bumped to invalidate ALL existing tokens for this user at once
    # (e.g. on password reset / token rotation — "logout everywhere").
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
