"""Revoked token model — JTI denylist for immediate logout / revocation.

Each issued JWT carries a unique `jti`. On logout we store that `jti` here
until the token would have expired anyway, so the auth dependency can reject it
even though the signature and `exp` are still technically valid.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    # The JWT ID (jti claim) — primary key so re-revoking is idempotent.
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # When the underlying token expires; rows past this are safe to purge.
    # Indexed (ix_revoked_tokens_expires_at) for the lazy cleanup query in
    # auth_service.revoke_token(); the index is created by migration 0004.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
