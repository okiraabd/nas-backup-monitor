"""Monitoring (metrics) request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.metric import SOURCE_CEPH, SOURCE_NAS


class MetricItem(BaseModel):
    """A single metric within an ingest payload.

    Exactly one of `value` (numeric) or `text` (string) is expected, though we
    accept both being present (text stored alongside value).
    """

    name: str = Field(..., max_length=64)
    value: float | None = None
    text: str | None = Field(None, max_length=255)
    unit: str | None = Field(None, max_length=32)


class MonitorIngest(BaseModel):
    """Payload sent by the collector to POST /api/monitor/ingest."""

    source_type: str
    source_id: str = Field(..., max_length=64)
    collected_at: datetime
    metrics: list[MetricItem] = Field(..., min_length=1)

    @field_validator("source_type")
    @classmethod
    def source_type_valid(cls, v: str) -> str:
        low = v.lower()
        if low not in {SOURCE_NAS, SOURCE_CEPH}:
            raise ValueError(f"source_type must be '{SOURCE_NAS}' or '{SOURCE_CEPH}'")
        return low


class MonitorIngestResponse(BaseModel):
    source_id: str
    stored_metrics: int
    status: str = "accepted"


class MetricValue(BaseModel):
    """A metric's latest value in a source snapshot."""
    value: float | None = None
    text: str | None = None
    unit: str | None = None


class SourceSnapshot(BaseModel):
    """Latest state of one source (NAS or Ceph) with computed freshness."""
    source_id: str
    display_name: str
    source_type: str
    last_collected_at: datetime | None = None
    staleness_seconds: int | None = None
    status: str  # fresh / stale / offline
    metrics: dict[str, MetricValue]


class HistoryPoint(BaseModel):
    collected_at: datetime
    value: float | None = None
    text: str | None = None


class MetricHistory(BaseModel):
    source_id: str
    metric_name: str
    points: list[HistoryPoint]


class NasListResponse(BaseModel):
    items: list[SourceSnapshot]


class MonitorSummary(BaseModel):
    total_nas: int
    nas_fresh: int
    nas_stale: int
    nas_offline: int
    ceph_status: str          # freshness of ceph source
    ceph_health: str | None = None  # HEALTH_OK etc. from metric_text
    storage_used_pct: float | None = None


class CollectorStatus(BaseModel):
    last_run_at: datetime | None = None
    last_status: str | None = None
    is_mock: bool = False
    total_sources: int = 0
    success_sources: int = 0
    failed_sources: int = 0
    message: str | None = None


class ActivityDay(BaseModel):
    date: str
    success: int = 0
    failed: int = 0


class ActivityTrendResponse(BaseModel):
    days: list[ActivityDay]


class CollectorRunRequest(BaseModel):
    """Payload sent by the collector to record its execution result."""
    started_at: datetime
    finished_at: datetime
    status: str
    is_mock: bool
    total_sources: int
    success_sources: int
    failed_sources: int
    message: str | None = None
