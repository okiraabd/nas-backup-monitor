"""Timezone helpers.

The API stores and compares instants in UTC. Presentation/business-day
boundaries for this project use the configured local timezone.
"""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.config import settings


def app_zone() -> ZoneInfo:
    """Return the configured local timezone, e.g. Asia/Jakarta."""
    return ZoneInfo(settings.app_timezone)


def local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """Return UTC instants that cover one local calendar day inclusively."""
    zone = app_zone()
    start_local = datetime.combine(day, time.min, tzinfo=zone)
    end_local = datetime.combine(day, time.max, tzinfo=zone)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def local_date_range_bounds_utc(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """Return UTC instants that cover an inclusive local date range."""
    start, _ = local_day_bounds_utc(date_from)
    _, end = local_day_bounds_utc(date_to)
    return start, end


def format_local_datetime(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format a datetime in the configured local timezone for reports/PDF."""
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(app_zone()).strftime(fmt)
