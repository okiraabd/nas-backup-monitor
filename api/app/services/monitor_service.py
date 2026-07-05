"""Monitoring service — freshness computation and metric aggregation.

Freshness thresholds (computed by the API, never the frontend):
    fresh   = staleness <= 90 seconds
    stale   = 90 < staleness <= 300 seconds (5 minutes)
    offline = staleness > 300 seconds, or no data at all
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metric import SOURCE_CEPH, SOURCE_NAS, Metric

FRESH_THRESHOLD_SECONDS = 90
STALE_THRESHOLD_SECONDS = 300

STATUS_FRESH = "fresh"
STATUS_STALE = "stale"
STATUS_OFFLINE = "offline"

# Human-friendly display names for known sources.
DISPLAY_NAMES = {
    "synology-ds1522": "Synology DS1522+",
    "wd-pr4100": "WD PR4100",
    "ceph-cluster": "Ceph Cluster",
}


def display_name_for(source_id: str) -> str:
    return DISPLAY_NAMES.get(source_id, source_id)


def compute_status(last_collected_at: datetime | None, now: datetime | None = None) -> tuple[str, int | None]:
    """Return (status, staleness_seconds) for a source's last collection time."""
    if last_collected_at is None:
        return STATUS_OFFLINE, None
    now = now or datetime.now(timezone.utc)
    # Ensure tz-aware comparison.
    if last_collected_at.tzinfo is None:
        last_collected_at = last_collected_at.replace(tzinfo=timezone.utc)
    staleness = int((now - last_collected_at).total_seconds())
    staleness = max(staleness, 0)
    if staleness <= FRESH_THRESHOLD_SECONDS:
        return STATUS_FRESH, staleness
    if staleness <= STALE_THRESHOLD_SECONDS:
        return STATUS_STALE, staleness
    return STATUS_OFFLINE, staleness


def list_source_ids(db: Session, source_type: str) -> list[str]:
    """Distinct source_ids seen for a given source_type."""
    rows = db.scalars(
        select(Metric.source_id)
        .where(Metric.source_type == source_type)
        .distinct()
    ).all()
    return sorted(rows)


def latest_snapshot(db: Session, source_type: str, source_id: str) -> dict | None:
    """Build the latest metric snapshot for one source.

    Returns a dict matching SourceSnapshot, or None if the source has no data.
    Picks the most recent value per metric_name.
    """
    rows = db.scalars(
        select(Metric)
        .where(Metric.source_type == source_type, Metric.source_id == source_id)
        .order_by(Metric.collected_at.desc(), Metric.id.desc())
    ).all()
    if not rows:
        return None

    metrics: dict[str, dict] = {}
    last_collected_at: datetime | None = None
    for m in rows:
        if last_collected_at is None:
            last_collected_at = m.collected_at
        if m.metric_name not in metrics:  # first seen = most recent (desc order)
            metrics[m.metric_name] = {
                "value": float(m.metric_value) if m.metric_value is not None else None,
                "text": m.metric_text,
                "unit": m.unit,
            }

    status, staleness = compute_status(last_collected_at)
    return {
        "source_id": source_id,
        "display_name": display_name_for(source_id),
        "source_type": source_type,
        "last_collected_at": last_collected_at,
        "staleness_seconds": staleness,
        "status": status,
        "metrics": metrics,
    }


def metric_history(
    db: Session, source_type: str, source_id: str, metric_name: str, limit: int = 50
) -> list[dict]:
    """Return time-ordered history points for one metric of one source."""
    rows = db.scalars(
        select(Metric)
        .where(
            Metric.source_type == source_type,
            Metric.source_id == source_id,
            Metric.metric_name == metric_name,
        )
        .order_by(Metric.collected_at.desc())
        .limit(limit)
    ).all()
    points = [
        {
            "collected_at": m.collected_at,
            "value": float(m.metric_value) if m.metric_value is not None else None,
            "text": m.metric_text,
        }
        for m in reversed(rows)  # chronological ascending for charts
    ]
    return points
