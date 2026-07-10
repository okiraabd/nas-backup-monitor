"""Monitoring (metrics) request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.metric import SOURCE_CEPH, SOURCE_NAS


def _is_aware(value: datetime) -> bool:
    """Return True when a datetime carries an explicit timezone offset."""
    return value.tzinfo is not None and value.utcoffset() is not None


class MetricItem(BaseModel):
    """A single metric within an ingest payload.

    Exactly one of `value` (numeric) or `text` (string) is expected, though we
    accept both being present (text stored alongside value).
    """

    name: str = Field(..., min_length=1, max_length=64, description="Metric name, e.g. cpu_usage.")
    value: float | None = Field(None, description="Numeric metric value.")
    text: str | None = Field(None, max_length=255, description="Text metric value, e.g. HEALTH_OK.")
    unit: str | None = Field(None, max_length=32, description="Display unit such as %, bytes, status, or count.")

    @field_validator("text", mode="before")
    @classmethod
    def blank_text_is_absent(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def value_or_text_required(self) -> "MetricItem":
        if self.value is None and self.text is None:
            raise ValueError("metric item must include value or text")
        return self


class MonitorIngest(BaseModel):
    """Payload sent by the collector to POST /api/monitor/ingest."""

    source_type: str = Field(..., min_length=1, description="Metric source type: nas or ceph.")
    source_id: str = Field(..., min_length=1, max_length=64, description="Stable source identifier.")
    collected_at: datetime = Field(..., description="Collection time with timezone offset.")
    metrics: list[MetricItem] = Field(..., min_length=1, description="Metric samples collected in this run.")

    @field_validator("source_type")
    @classmethod
    def source_type_valid(cls, v: str) -> str:
        low = v.strip().lower()
        if low not in {SOURCE_NAS, SOURCE_CEPH}:
            raise ValueError(f"source_type must be '{SOURCE_NAS}' or '{SOURCE_CEPH}'")
        return low

    @field_validator("collected_at")
    @classmethod
    def collected_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if not _is_aware(value):
            raise ValueError("collected_at must include timezone information")
        return value


class MonitorIngestResponse(BaseModel):
    """Result returned after metric samples are stored."""

    source_id: str = Field(..., description="Source identifier from the ingest payload.")
    stored_metrics: int = Field(..., description="Number of metric rows stored.")
    status: str = Field("accepted", description="Ingest acceptance status.")


class MetricValue(BaseModel):
    """A metric's latest value in a source snapshot."""
    value: float | None = Field(None, description="Latest numeric value, if any.")
    text: str | None = Field(None, description="Latest text value, if any.")
    unit: str | None = Field(None, description="Metric display unit.")


class SourceSnapshot(BaseModel):
    """Latest state of one source (NAS or Ceph) with computed freshness."""
    source_id: str = Field(..., description="Stable source identifier.")
    display_name: str = Field(..., description="Human-readable source name.")
    source_type: str = Field(..., description="Source type: nas or ceph.")
    last_collected_at: datetime | None = Field(None, description="Newest metric timestamp for this source.")
    staleness_seconds: int | None = Field(None, description="Age of the newest metric in seconds.")
    status: str = Field(..., description="Freshness status: fresh, stale, or offline.")
    metrics: dict[str, MetricValue] = Field(..., description="Latest value per metric name.")


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
    started_at: datetime = Field(..., description="Collector run start time with timezone offset.")
    finished_at: datetime = Field(..., description="Collector run finish time with timezone offset.")
    status: str = Field(..., description="Run status: SUCCESS, PARTIAL_FAILED, or FAILED.")
    is_mock: bool = Field(..., description="True if the collector used mock/demo data.")
    total_sources: int = Field(..., ge=0, description="Number of sources attempted.")
    success_sources: int = Field(..., ge=0, description="Number of sources collected successfully.")
    failed_sources: int = Field(..., ge=0, description="Number of sources that failed collection.")
    message: str | None = Field(None, description="Short collector run summary.")

    @field_validator("started_at", "finished_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if not _is_aware(value):
            raise ValueError("datetime must include timezone information")
        return value

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, value: str) -> str:
        status = value.strip().upper()
        if status not in {"SUCCESS", "PARTIAL_FAILED", "FAILED"}:
            raise ValueError("status must be SUCCESS, PARTIAL_FAILED, or FAILED")
        return status

    @model_validator(mode="after")
    def validate_run_consistency(self) -> "CollectorRunRequest":
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must be on or after started_at")
        if self.success_sources + self.failed_sources > self.total_sources:
            raise ValueError("success_sources + failed_sources cannot exceed total_sources")
        return self
