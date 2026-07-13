"""Collector run model — tracks each execution of the metric collector."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# statuses: PENDING (run-once marker) / SUCCESS / PARTIAL_FAILED / FAILED
# modes:    demo / real / hybrid

# Statuses a collector may report when recording a finished run. The PENDING
# marker is written server-side by the run-once endpoint, not reported here.
VALID_COLLECTOR_STATUSES = {"SUCCESS", "PARTIAL_FAILED", "FAILED"}


class CollectorRun(Base):
    __tablename__ = "collector_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_sources: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_sources: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_sources: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
