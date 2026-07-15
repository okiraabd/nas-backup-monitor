"""Monitoring router: ingest (collector), summaries + history (admin)."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin, require_collector, require_roles
from app.models.collector_run import CollectorRun
from app.models.metric import SOURCE_CEPH, SOURCE_NAS, Metric
from app.models.user import User
from app.models.backup_log import BackupLog
from app.config import settings
from app.schemas.monitor import (
    ActivityDay,
    ActivityTrendResponse,
    CollectorRunRequest,
    CollectorStatus,
    MetricHistory,
    MonitorIngest,
    MonitorIngestResponse,
    MonitorSummary,
    NasListResponse,
    SourceSnapshot,
)
from app.services import monitor_service as svc
from app.timezone import app_zone, local_day_bounds_utc

router = APIRouter(prefix="/monitor", tags=["monitor"])

# Admin OR collector may read collector status; both dashboard and collector need it.
require_admin_operator_or_collector = require_roles("admin", "operator", "collector")


@router.post(
    "/ingest",
    response_model=MonitorIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest NAS/Ceph metric samples",
)
def ingest_metrics(
    payload: MonitorIngest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_collector),
) -> MonitorIngestResponse:
    """Ingest a batch of metrics. Role: collector only.

    Each metric is stored as its own row (numeric -> metric_value,
    string -> metric_text).
    """
    # Store samples independently so history queries can chart each metric name.
    stored = 0
    for item in payload.metrics:
        db.add(
            Metric(
                collected_at=payload.collected_at,
                source_type=payload.source_type,
                source_id=payload.source_id,
                metric_name=item.name,
                metric_value=item.value,
                metric_text=item.text,
                unit=item.unit,
                collected_by=current_user.id,
            )
        )
        stored += 1
    db.commit()
    return MonitorIngestResponse(source_id=payload.source_id, stored_metrics=stored)


@router.get(
    "/summary",
    response_model=MonitorSummary,
    summary="Get monitoring summary",
)
def summary(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
) -> MonitorSummary:
    """Aggregate NAS freshness counts + Ceph health. Role: admin/operator."""
    # Summary is computed from the latest snapshot per source, not from cached rows.
    nas_ids = svc.list_source_ids(db, SOURCE_NAS)
    counts = {svc.STATUS_FRESH: 0, svc.STATUS_STALE: 0, svc.STATUS_OFFLINE: 0}
    for sid in nas_ids:
        snap = svc.latest_snapshot(db, SOURCE_NAS, sid)
        if snap:
            counts[snap["status"]] += 1

    ceph_snap = svc.latest_snapshot(db, SOURCE_CEPH, "ceph-cluster")
    ceph_status = ceph_snap["status"] if ceph_snap else svc.STATUS_OFFLINE
    ceph_health = None
    storage_used_pct = None
    if ceph_snap:
        health = ceph_snap["metrics"].get("health_status")
        ceph_health = health["text"] if health else None
        used = ceph_snap["metrics"].get("storage_used_pct")
        storage_used_pct = used["value"] if used else None

    return MonitorSummary(
        total_nas=len(nas_ids),
        nas_fresh=counts[svc.STATUS_FRESH],
        nas_stale=counts[svc.STATUS_STALE],
        nas_offline=counts[svc.STATUS_OFFLINE],
        ceph_status=ceph_status,
        ceph_health=ceph_health,
        storage_used_pct=storage_used_pct,
    )


@router.get(
    "/activity-trend",
    response_model=ActivityTrendResponse,
    summary="Get seven-day backup activity trend",
)
def activity_trend(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
) -> ActivityTrendResponse:
    """Get backup success/failure trend for the last 7 days. Role: admin/operator."""
    bind = db.get_bind()
    dialect = bind.dialect.name if bind is not None else ""
    if dialect == "postgresql":
        date_expr = cast(func.timezone(settings.app_timezone, BackupLog.created_at), Date)
    else:
        # SQLite test/dev fallback. Asia/Jakarta is UTC+07 with no DST.
        date_expr = func.date(BackupLog.created_at, "+7 hours")

    # Query the last 7 local calendar days, not the last 7 UTC days.
    today_local = datetime.now(timezone.utc).astimezone(app_zone()).date()
    start_date = today_local - timedelta(days=6)
    seven_days_ago, _ = local_day_bounds_utc(start_date)

    results = db.execute(
        select(
            date_expr.label("log_date"),
            func.sum(case((BackupLog.status == "SUCCESS", 1), else_=0)).label("success_count"),
            func.sum(case((BackupLog.status == "FAILED", 1), else_=0)).label("failed_count"),
        )
        .where(BackupLog.created_at >= seven_days_ago)
        .group_by("log_date")
        .order_by("log_date")
    ).all()
    
    days = []
    for r in results:
        days.append(ActivityDay(
            date=str(r.log_date),
            success=r.success_count or 0,
            failed=r.failed_count or 0
        ))
        
    # If no data, return empty list (frontend handles padding if necessary, or just shows empty)
    return ActivityTrendResponse(days=days)


@router.get(
    "/nas",
    response_model=NasListResponse,
    summary="List monitored NAS sources",
)
def list_nas(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
) -> NasListResponse:
    """List all NAS sources with latest snapshot + freshness. Role: admin/operator."""
    snaps = []
    for sid in svc.list_source_ids(db, SOURCE_NAS):
        snap = svc.latest_snapshot(db, SOURCE_NAS, sid)
        if snap:
            snaps.append(SourceSnapshot.model_validate(snap))
    return NasListResponse(items=snaps)


@router.get(
    "/nas/{nas_id}",
    response_model=SourceSnapshot,
    summary="Get latest NAS snapshot",
)
def get_nas(
    nas_id: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
) -> SourceSnapshot:
    """Latest snapshot for one NAS. Role: admin/operator."""
    snap = svc.latest_snapshot(db, SOURCE_NAS, nas_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="NAS source not found")
    return SourceSnapshot.model_validate(snap)


@router.get(
    "/nas/{nas_id}/history",
    response_model=MetricHistory,
    summary="Get NAS metric history",
)
def get_nas_history(
    nas_id: str,
    metric: str = Query("cpu_usage"),
    limit: int = Query(50, ge=1, le=500),
    max_points: int = Query(300, ge=2, le=1000, description="Maximum chart points returned for a time range."),
    hours: int | None = Query(None, ge=1, le=8760, description="Fetch last N hours of data (overrides limit)."),
    date_from: datetime | None = Query(None, description="Filter history from this datetime (UTC)."),
    date_to: datetime | None = Query(None, description="Filter history up to this datetime (UTC)."),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
) -> MetricHistory:
    """History of one metric for one NAS. Role: admin/operator."""
    if hours is not None:
        # Relative range is a convenience alias; explicit date_from/date_to still
        # flow through to the shared history service.
        date_from = datetime.now(timezone.utc) - timedelta(hours=hours)
    points = svc.metric_history(
        db,
        SOURCE_NAS,
        nas_id,
        metric,
        limit,
        date_from=date_from,
        date_to=date_to,
        max_points=max_points,
    )
    return MetricHistory(source_id=nas_id, metric_name=metric, points=points)


@router.get(
    "/ceph",
    response_model=SourceSnapshot,
    summary="Get latest Ceph snapshot",
)
def get_ceph(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
    source_id: str = Query("ceph-cluster"),
) -> SourceSnapshot:
    """Latest snapshot for the Ceph cluster. Role: admin/operator."""
    snap = svc.latest_snapshot(db, SOURCE_CEPH, source_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Ceph source not found")
    return SourceSnapshot.model_validate(snap)


@router.get(
    "/ceph/history",
    response_model=MetricHistory,
    summary="Get Ceph metric history",
)
def get_ceph_history(
    metric: str = Query("storage_used_pct"),
    limit: int = Query(50, ge=1, le=500),
    max_points: int = Query(300, ge=2, le=1000, description="Maximum chart points returned for a time range."),
    hours: int | None = Query(None, ge=1, le=8760, description="Fetch last N hours of data (overrides limit)."),
    date_from: datetime | None = Query(None, description="Filter history from this datetime (UTC)."),
    date_to: datetime | None = Query(None, description="Filter history up to this datetime (UTC)."),
    source_id: str = Query("ceph-cluster"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
) -> MetricHistory:
    """History of one metric for the Ceph cluster. Role: admin/operator."""
    if hours is not None:
        # Keep Ceph history semantics identical to NAS history.
        date_from = datetime.now(timezone.utc) - timedelta(hours=hours)
    points = svc.metric_history(
        db,
        SOURCE_CEPH,
        source_id,
        metric,
        limit,
        date_from=date_from,
        date_to=date_to,
        max_points=max_points,
    )
    return MetricHistory(source_id=source_id, metric_name=metric, points=points)


@router.get(
    "/collector/status",
    response_model=CollectorStatus,
    summary="Get last collector run status",
)
def collector_status(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin_operator_or_collector),
) -> CollectorStatus:
    """Most recent collector run status. Role: admin/operator/collector."""
    run = db.scalar(select(CollectorRun).order_by(CollectorRun.created_at.desc()))
    if run is None:
        return CollectorStatus()
    return CollectorStatus(
        last_run_at=run.finished_at or run.started_at,
        last_status=run.status,
        is_mock=run.is_mock,
        total_sources=run.total_sources,
        success_sources=run.success_sources,
        failed_sources=run.failed_sources,
        message=run.message,
    )


@router.post(
    "/collector/run-once",
    response_model=CollectorStatus,
    status_code=202,
    summary="Record a manual collector trigger",
)
def collector_run_once(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
) -> CollectorStatus:
    """Record a manual collector trigger request. Role: admin/operator.

    In this stage the collector runs as a separate process; this endpoint
    records the intent as a RUNNING collector_run so the dashboard can reflect
    that a run was requested. The real collector (stage 6) will update it.
    """
    # The collector daemon watches for this PENDING marker during its wait loop.
    run = CollectorRun(
        started_at=datetime.now(timezone.utc),
        status="PENDING",
        is_mock=False,
        message="Manual run requested from dashboard",
        total_sources=0,
        success_sources=0,
        failed_sources=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return CollectorStatus(
        last_run_at=run.started_at,
        last_status=run.status,
        is_mock=run.is_mock,
        total_sources=run.total_sources,
        success_sources=run.success_sources,
        failed_sources=run.failed_sources,
        message=run.message,
    )


@router.post(
    "/collector/run",
    response_model=CollectorStatus,
    status_code=201,
    summary="Record a completed collector run",
)
def collector_run_report(
    payload: CollectorRunRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_collector),
) -> CollectorStatus:
    """Record a completed collector run. Role: collector."""
    # CollectorRun is process-level status; this model currently has no user FK.
    run = CollectorRun(
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        status=payload.status,
        is_mock=payload.is_mock,
        message=payload.message,
        total_sources=payload.total_sources,
        success_sources=payload.success_sources,
        failed_sources=payload.failed_sources,
    )
    db.add(run)
    db.commit()
    return CollectorStatus(
        last_run_at=run.finished_at,
        last_status=run.status,
        is_mock=run.is_mock,
        total_sources=run.total_sources,
        success_sources=run.success_sources,
        failed_sources=run.failed_sources,
        message=run.message,
    )
