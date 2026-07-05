"""Metric model — one row per individual metric sample (NAS or Ceph)."""
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

SOURCE_NAS = "nas"
SOURCE_CEPH = "ceph"


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)  # nas / ceph
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    metric_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    collected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_metrics_source_name_time", "source_id", "metric_name", "collected_at"),
        Index("ix_metrics_type_source_time", "source_type", "source_id", "collected_at"),
    )
