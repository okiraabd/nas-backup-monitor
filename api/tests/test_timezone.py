"""Timezone helper tests."""
from datetime import date

from app.timezone import local_day_bounds_utc


def test_jakarta_day_bounds_are_converted_to_utc():
    start, end = local_day_bounds_utc(date(2026, 7, 10))

    assert start.isoformat() == "2026-07-09T17:00:00+00:00"
    assert end.isoformat() == "2026-07-10T16:59:59.999999+00:00"
