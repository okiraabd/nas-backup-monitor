"""Backup log model — one row per Kopia snapshot result ingested from a NAS."""
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# JSONB on PostgreSQL (production), plain JSON elsewhere (e.g. SQLite in tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")

STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"
VALID_STATUSES = {STATUS_SUCCESS, STATUS_FAILED}


class BackupLog(Base):
    __tablename__ = "backup_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nas_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    job_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    destination_target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    backup_engine: Mapped[str] = mapped_column(String(32), default="kopia", nullable=False)
    status: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_files: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changed_file_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_files: Mapped[int | None] = mapped_column(Integer, nullable=True)
    non_cached_files: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dir_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ignored_error_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    retention_reason: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    reported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Acknowledge workflow (for FAILED logs)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
