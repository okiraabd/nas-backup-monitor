"""Schema helpers shared across request/response models."""
from datetime import datetime

from pydantic import BaseModel, Field


def is_aware(value: datetime) -> bool:
    """Return True when a datetime carries an explicit timezone offset."""
    return value.tzinfo is not None and value.utcoffset() is not None


class BulkDeleteResponse(BaseModel):
    """Result of a bulk delete operation (logs or reports)."""

    deleted_count: int = Field(..., description="Number of rows permanently deleted.")
