"""Backup logs router: ingest (service), list/detail/acknowledge (admin)."""
from datetime import datetime, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin, require_service
from app.models.backup_log import STATUS_FAILED, BackupLog
from app.models.user import User
from app.schemas.log import (
    AcknowledgeRequest,
    LogDetail,
    LogIngest,
    LogIngestResponse,
    LogSummaryItem,
    PaginatedLogs,
)

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post(
    "/ingest",
    response_model=LogIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_log(
    payload: LogIngest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service),
) -> LogIngestResponse:
    """Ingest a backup result from a NAS. Role: service only."""
    log = BackupLog(
        nas_id=payload.nas_id,
        job_name=payload.job_name,
        source_path=payload.source_path,
        source_ip=payload.source_ip,
        destination_target=payload.destination_target,
        backup_engine=payload.backup_engine or "kopia",
        status=payload.status,
        snapshot_id=payload.snapshot_id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        duration_seconds=payload.duration_seconds,
        total_size_bytes=payload.total_size_bytes,
        total_files=payload.total_files,
        changed_file_count=payload.changed_file_count,
        cached_files=payload.cached_files,
        non_cached_files=payload.non_cached_files,
        dir_count=payload.dir_count,
        error_count=payload.error_count,
        ignored_error_count=payload.ignored_error_count,
        retention_reason=payload.retention_reason,
        message=payload.message,
        raw_payload=payload.raw_payload,
        reported_by=current_user.id,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return LogIngestResponse(
        log_id=log.id, received_at=log.created_at, status=log.status
    )


@router.get("", response_model=PaginatedLogs)
def list_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
    nas_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    job_name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    acknowledged: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedLogs:
    """List backup logs with filters + pagination. Role: admin/operator."""
    conditions = []
    if nas_id:
        conditions.append(BackupLog.nas_id == nas_id)
    if status_filter:
        conditions.append(BackupLog.status == status_filter.upper())
    if job_name:
        conditions.append(BackupLog.job_name == job_name)
    if date_from:
        conditions.append(BackupLog.created_at >= date_from)
    if date_to:
        conditions.append(BackupLog.created_at <= date_to)
    if acknowledged is not None:
        conditions.append(BackupLog.acknowledged == acknowledged)

    total = db.scalar(
        select(func.count()).select_from(BackupLog).where(*conditions)
    ) or 0

    rows = db.scalars(
        select(BackupLog)
        .where(*conditions)
        .order_by(BackupLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedLogs(
        items=[LogSummaryItem.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if page_size else 0,
    )


@router.get("/{log_id}", response_model=LogDetail)
def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> LogDetail:
    """Get a single backup log's full detail. Role: admin/operator."""
    log = db.get(BackupLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return LogDetail.model_validate(log)


@router.patch("/{log_id}/acknowledge", response_model=LogDetail)
def acknowledge_log(
    log_id: int,
    payload: AcknowledgeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> LogDetail:
    """Acknowledge a FAILED backup log with a remark. Role: admin/operator."""
    log = db.get(BackupLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    if log.status != STATUS_FAILED:
        raise HTTPException(
            status_code=400,
            detail="Only FAILED logs need acknowledgement",
        )
    log.acknowledged = True
    log.acknowledged_by = current_user.id
    log.acknowledged_at = datetime.now(timezone.utc)
    log.remark = payload.remark
    db.commit()
    db.refresh(log)
    return LogDetail.model_validate(log)
