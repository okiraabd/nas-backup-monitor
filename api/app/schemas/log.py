"""Backup log request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.backup_log import VALID_STATUSES


def _is_aware(value: datetime) -> bool:
    """Return True when a datetime carries an explicit timezone offset."""
    return value.tzinfo is not None and value.utcoffset() is not None


class LogIngest(BaseModel):
    """Payload sent by the Kopia NAS script to POST /api/logs/ingest."""

    nas_id: str = Field(..., min_length=1, max_length=64, description="Stable NAS/source identifier.")
    job_name: str = Field(..., min_length=1, max_length=128, description="Backup job or policy name.")
    source_path: str | None = Field(None, max_length=512, description="Path that was backed up on the NAS.")
    source_ip: str | None = Field(None, max_length=64, description="NAS IP address observed by the reporter.")
    destination_target: str | None = Field(None, max_length=128, description="Backup destination label, e.g. Ceph S3.")
    backup_engine: str = Field("kopia", min_length=1, max_length=32, description="Backup engine name.")
    status: str = Field(..., min_length=1, description="Backup result: SUCCESS or FAILED.")
    snapshot_id: str | None = Field(None, max_length=128, description="Kopia snapshot ID. Used for idempotent retry handling.")
    started_at: datetime | None = Field(None, description="Backup start time with timezone offset.")
    ended_at: datetime | None = Field(None, description="Backup end time with timezone offset.")
    duration_seconds: int | None = Field(None, ge=0, description="Backup duration in seconds.")
    total_size_bytes: int | None = Field(None, ge=0, description="Total protected data size in bytes.")
    total_files: int | None = Field(None, ge=0, description="Total file count reported by Kopia.")
    changed_file_count: int | None = Field(None, ge=0, description="Number of changed files in the snapshot.")
    cached_files: int | None = Field(None, ge=0, description="Number of files reused from repository cache.")
    non_cached_files: int | None = Field(None, ge=0, description="Number of files newly uploaded or processed.")
    dir_count: int | None = Field(None, ge=0, description="Directory count reported by Kopia.")
    error_count: int | None = Field(None, ge=0, description="Number of backup errors.")
    ignored_error_count: int | None = Field(None, ge=0, description="Number of ignored/non-fatal errors.")
    retention_reason: list | None = Field(None, description="Retention labels/reasons returned by Kopia.")
    message: str | None = Field(None, description="Short success or failure message.")
    raw_payload: dict | None = Field(None, description="Original reporter payload for troubleshooting.")

    @field_validator("snapshot_id", mode="before")
    @classmethod
    def blank_snapshot_id_is_absent(cls, value: str | None) -> str | None:
        """Treat blank snapshot IDs like missing IDs so retries stay event-based."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        up = v.strip().upper()
        if up not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return up

    @field_validator("started_at", "ended_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        """Require explicit timezone offsets; the API stores instants in UTC."""
        if value is not None and not _is_aware(value):
            raise ValueError("datetime must include timezone information")
        return value

    @model_validator(mode="after")
    def ended_at_must_not_precede_started_at(self) -> "LogIngest":
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError("ended_at must be on or after started_at")
        return self


class LogIngestResponse(BaseModel):
    """Result returned after the API accepts or deduplicates a backup log."""

    log_id: int = Field(..., description="Backup log row ID.")
    received_at: datetime = Field(..., description="Server-side receive/create timestamp.")
    status: str = Field(..., description="Stored backup status.")
    created: bool = Field(True, description="False when a retry matched an existing snapshot.")


class LogSummaryItem(BaseModel):
    """Row shape for the paginated log list."""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Backup log row ID.")
    nas_id: str = Field(..., description="NAS/source identifier.")
    job_name: str = Field(..., description="Backup job or policy name.")
    status: str = Field(..., description="Backup result: SUCCESS or FAILED.")
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
    """Operator note used when reviewing a failed backup."""

    remark: str = Field(..., min_length=1, max_length=2000, description="Review note explaining the failure handling.")


class BulkDeleteRequest(BaseModel):
    """Request body for DELETE /logs/bulk."""

    log_ids: list[int] | None = Field(
        None, description="Specific log IDs to delete. Optional."
    )
    date_from: datetime | None = Field(
        None, description="Delete logs created on or after this datetime (UTC). Optional."
    )
    date_to: datetime | None = Field(
        None, description="Delete logs created on or before this datetime (UTC). Optional."
    )


class BulkDeleteResponse(BaseModel):
    """Result of a bulk delete operation."""

    deleted_count: int = Field(..., description="Number of log rows permanently deleted.")
