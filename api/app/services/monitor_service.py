"""Monitoring service — freshness computation and metric aggregation.

Freshness thresholds (computed by the API, never the frontend):
    fresh   = staleness <= 90 seconds
    stale   = 90 < staleness <= 300 seconds (5 minutes)
    offline = staleness > 300 seconds, or no data at all
"""
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

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
    # Rank rows inside the database so we only fetch the newest row for each
    # metric_name. This keeps dashboard reads fast as metric history grows.
    ranked_metrics = (
        select(
            Metric,
            func.row_number()
            .over(
                partition_by=Metric.metric_name,
                order_by=(Metric.collected_at.desc(), Metric.id.desc()),
            )
            .label("row_number"),
        )
        .where(Metric.source_type == source_type, Metric.source_id == source_id)
        .subquery()
    )
    latest_metric = aliased(Metric, ranked_metrics)

    rows = db.scalars(
        select(latest_metric)
        .where(ranked_metrics.c.row_number == 1)
        .order_by(latest_metric.collected_at.desc(), latest_metric.id.desc())
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
    db: Session,
    source_type: str,
    source_id: str,
    metric_name: str,
    limit: int = 50,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    max_points: int = 300,
) -> list[dict]:
    """Return time-ordered history points for one metric of one source.

    Range queries are sampled evenly inside the database and always retain the
    first and last sample. Non-range queries preserve the existing latest-N
    behavior controlled by ``limit``.
    """
    filters = (
        Metric.source_type == source_type,
        Metric.source_id == source_id,
        Metric.metric_name == metric_name,
    )
    if date_from is not None:
        filters += (Metric.collected_at >= date_from,)
    if date_to is not None:
        filters += (Metric.collected_at <= date_to,)

    point_columns = (Metric.collected_at, Metric.metric_value, Metric.metric_text)
    is_range_query = date_from is not None or date_to is not None

    if not is_range_query:
        rows = db.execute(
            select(*point_columns)
            .where(*filters)
            .order_by(Metric.collected_at.desc(), Metric.id.desc())
            .limit(limit)
        ).all()
        rows.reverse()
    else:
        total = db.scalar(select(func.count(Metric.id)).where(*filters)) or 0
        if total <= max_points:
            rows = db.execute(
                select(*point_columns)
                .where(*filters)
                .order_by(Metric.collected_at.asc(), Metric.id.asc())
            ).all()
        else:
            stride = ceil((total - 1) / (max_points - 1))
            ranked = (
                select(
                    *point_columns,
                    func.row_number()
                    .over(order_by=(Metric.collected_at.asc(), Metric.id.asc()))
                    .label("point_number"),
                )
                .where(*filters)
                .subquery()
            )
            rows = db.execute(
                select(
                    ranked.c.collected_at,
                    ranked.c.metric_value,
                    ranked.c.metric_text,
                )
                .where(
                    or_(
                        ranked.c.point_number == 1,
                        ranked.c.point_number == total,
                        (ranked.c.point_number - 1) % stride == 0,
                    )
                )
                .order_by(ranked.c.collected_at.asc(), ranked.c.point_number.asc())
            ).all()

    points = [
        {
            "collected_at": row.collected_at,
            "value": float(row.metric_value) if row.metric_value is not None else None,
            "text": row.metric_text,
        }
        for row in rows
    ]
    return points
