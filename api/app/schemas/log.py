"""Backup log request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.backup_log import VALID_STATUSES


class LogIngest(BaseModel):
    """Payload sent by the Kopia NAS script to POST /api/logs/ingest."""

    nas_id: str = Field(..., max_length=64)
    job_name: str = Field(..., max_length=128)
    source_path: str | None = Field(None, max_length=512)
    source_ip: str | None = Field(None, max_length=64)
    destination_target: str | None = Field(None, max_length=128)
    backup_engine: str = Field("kopia", max_length=32)
    status: str
    snapshot_id: str | None = Field(None, max_length=128)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    total_size_bytes: int | None = None
    total_files: int | None = None
    changed_file_count: int | None = None
    cached_files: int | None = None
    non_cached_files: int | None = None
    dir_count: int | None = None
    error_count: int | None = None
    ignored_error_count: int | None = None
    retention_reason: list | None = None
    message: str | None = None
    raw_payload: dict | None = None

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        up = v.upper()
        if up not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return up


class LogIngestResponse(BaseModel):
    log_id: int
    received_at: datetime
    status: str
    created: bool = True


class LogSummaryItem(BaseModel):
    """Row shape for the paginated log list."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nas_id: str
    job_name: str
    status: str
    snapshot_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    total_size_bytes: int | None = None
    error_count: int | None = None
    acknowledged: bool
    created_at: datetime


class LogDetail(LogSummaryItem):
    """Full log detail (adds the heavier fields)."""

    source_path: str | None = None
    source_ip: str | None = None
    destination_target: str | None = None
    backup_engine: str
    total_files: int | None = None
    changed_file_count: int | None = None
    cached_files: int | None = None
    non_cached_files: int | None = None
    dir_count: int | None = None
    ignored_error_count: int | None = None
    retention_reason: list | None = None
    message: str | None = None
    raw_payload: dict | None = None
    reported_by: int | None = None
    acknowledged_by: int | None = None
    acknowledged_at: datetime | None = None
    remark: str | None = None


class PaginatedLogs(BaseModel):
    items: list[LogSummaryItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class AcknowledgeRequest(BaseModel):
    remark: str = Field(..., min_length=1, max_length=2000)
