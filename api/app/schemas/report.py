"""Report request/response schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportGenerate(BaseModel):
    """Request body for generating a PDF backup report."""

    date_from: date = Field(..., description="Start date of the report period, interpreted in APP_TIMEZONE.")
    date_to: date = Field(..., description="End date of the report period, interpreted in APP_TIMEZONE.")
    nas_id: str | None = Field(None, description="Optional NAS filter. Omit to include all NAS sources.")
    custom_name: str | None = Field(None, description="Optional filename prefix; unsafe characters are sanitized.")
    sla_target: float = Field(99.5, ge=0, le=100, description="SLA target percentage (0–100). Default: 99.5%.")

    @model_validator(mode="after")
    def check_range(self) -> "ReportGenerate":
        if self.date_to < self.date_from:
            raise ValueError("date_to must be on or after date_from")
        return self


class ReportOut(BaseModel):
    """Metadata for a generated report file."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Report row ID.")
    filename: str = Field(..., description="PDF filename.")
    date_from: date = Field(..., description="Report start date.")
    date_to: date = Field(..., description="Report end date.")
    nas_filter: str | None = Field(None, description="NAS filter used to generate the report.")
    generated_by: int | None = Field(None, description="User ID that generated the report.")
    generated_at: datetime = Field(..., description="Server-side report generation time.")
    file_size_bytes: int | None = Field(None, description="PDF file size in bytes.")

class ReportBulkDelete(BaseModel):
    """Request body for bulk deleting reports."""
    report_ids: list[int] = Field(default_factory=list, description="List of report IDs to delete.")
    date_from: date | None = Field(None, description="Delete reports generated on or after this date.")
    date_to: date | None = Field(None, description="Delete reports generated on or before this date.")

class BulkDeleteResponse(BaseModel):
    deleted_count: int = Field(..., description="Number of reports deleted.")
