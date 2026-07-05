"""Monitoring router: ingest (collector), summaries + history (admin)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, cast, Date, case
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin, require_collector, require_roles
from app.models.collector_run import CollectorRun
from app.models.metric import SOURCE_CEPH, SOURCE_NAS, Metric
from app.models.user import User
from app.models.backup_log import BackupLog
from app.schemas.monitor import (
    CollectorRunRequest,
    CollectorStatus,
    MetricHistory,
    MonitorIngest,
    MonitorIngestResponse,
    MonitorSummary,
    NasListResponse,
    SourceSnapshot,
    ActivityTrendResponse,
    ActivityDay,
)
from app.services import monitor_service as svc
from datetime import timedelta

router = APIRouter(prefix="/monitor", tags=["monitor"])

# Admin OR collector may read collector status; both dashboard and collector need it.
require_admin_operator_or_collector = require_roles("admin", "operator", "collector")


@router.post(
    "/ingest",
    response_model=MonitorIngestResponse,
    status_code=status.HTTP_201_CREATED,
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


@router.get("/summary", response_model=MonitorSummary)
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> MonitorSummary:
    """Aggregate NAS freshness counts + Ceph health. Role: admin only."""
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


@router.get("/activity-trend", response_model=ActivityTrendResponse)
def activity_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> ActivityTrendResponse:
    """Get backup success/failure trend for the last 7 days. Role: admin/operator."""
    # SQLite friendly date truncation
    date_expr = func.date(BackupLog.created_at)
    
    # Query logs from the last 7 days
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
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


@router.get("/nas", response_model=NasListResponse)
def list_nas(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> NasListResponse:
    """List all NAS sources with latest snapshot + freshness. Role: admin."""
    snaps = []
    for sid in svc.list_source_ids(db, SOURCE_NAS):
        snap = svc.latest_snapshot(db, SOURCE_NAS, sid)
        if snap:
            snaps.append(SourceSnapshot.model_validate(snap))
    return NasListResponse(items=snaps)


@router.get("/nas/{nas_id}", response_model=SourceSnapshot)
def get_nas(
    nas_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> SourceSnapshot:
    """Latest snapshot for one NAS. Role: admin."""
    snap = svc.latest_snapshot(db, SOURCE_NAS, nas_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="NAS source not found")
    return SourceSnapshot.model_validate(snap)


@router.get("/nas/{nas_id}/history", response_model=MetricHistory)
def get_nas_history(
    nas_id: str,
    metric: str = Query("cpu_usage"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> MetricHistory:
    """History of one metric for one NAS. Role: admin."""
    points = svc.metric_history(db, SOURCE_NAS, nas_id, metric, limit)
    return MetricHistory(source_id=nas_id, metric_name=metric, points=points)


@router.get("/ceph", response_model=SourceSnapshot)
def get_ceph(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
    source_id: str = Query("ceph-cluster"),
) -> SourceSnapshot:
    """Latest snapshot for the Ceph cluster. Role: admin."""
    snap = svc.latest_snapshot(db, SOURCE_CEPH, source_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Ceph source not found")
    return SourceSnapshot.model_validate(snap)


@router.get("/ceph/history", response_model=MetricHistory)
def get_ceph_history(
    metric: str = Query("storage_used_pct"),
    limit: int = Query(50, ge=1, le=500),
    source_id: str = Query("ceph-cluster"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> MetricHistory:
    """History of one metric for the Ceph cluster. Role: admin."""
    points = svc.metric_history(db, SOURCE_CEPH, source_id, metric, limit)
    return MetricHistory(source_id=source_id, metric_name=metric, points=points)


@router.get("/collector/status", response_model=CollectorStatus)
def collector_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_operator_or_collector),
) -> CollectorStatus:
    """Most recent collector run status. Role: admin or collector."""
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


@router.post("/collector/run-once", response_model=CollectorStatus, status_code=202)
def collector_run_once(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> CollectorStatus:
    """Record a manual collector trigger request. Role: admin.

    In this stage the collector runs as a separate process; this endpoint
    records the intent as a RUNNING collector_run so the dashboard can reflect
    that a run was requested. The real collector (stage 6) will update it.
    """
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


@router.post("/collector/run", response_model=CollectorStatus, status_code=201)
def collector_run_report(
    payload: CollectorRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_collector),
) -> CollectorStatus:
    """Record a completed collector run. Role: collector."""
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
