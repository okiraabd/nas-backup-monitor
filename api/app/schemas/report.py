"""Report request/response schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, model_validator


class ReportGenerate(BaseModel):
    date_from: date
    date_to: date
    nas_id: str | None = None
    custom_name: str | None = None

    @model_validator(mode="after")
    def check_range(self) -> "ReportGenerate":
        if self.date_to < self.date_from:
            raise ValueError("date_to must be on or after date_from")
        return self


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    date_from: date
    date_to: date
    nas_filter: str | None = None
    generated_by: int | None = None
    generated_at: datetime
    file_size_bytes: int | None = None
