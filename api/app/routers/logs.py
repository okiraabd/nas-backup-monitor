"""Backup logs router: ingest (service), list/detail/acknowledge (admin)."""
from datetime import datetime, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin, require_service, require_admin
from app.models.backup_log import STATUS_FAILED, BackupLog
from app.models.user import User
from app.services.bulk_delete import build_bulk_delete_conditions
from app.schemas.log import (
    AcknowledgeRequest,
    BulkDeleteRequest,
    BulkDeleteResponse,
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
    summary="Ingest one NAS backup result",
)
def ingest_log(
    payload: LogIngest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service),
) -> LogIngestResponse:
    """Ingest a backup result from a NAS. Role: service only.

    A Kopia snapshot is idempotent on (nas_id, job_name, snapshot_id). A retry
    returns the existing row with HTTP 200 instead of creating a duplicate.
    Logs without a snapshot_id (for example, pre-snapshot failures) are always
    stored as separate events.
    """
    # Snapshot-bearing results are idempotent; synthetic failures without
    # snapshot_id intentionally remain event-based observations.
    if payload.snapshot_id is not None:
        existing = db.scalar(
            select(BackupLog).where(
                BackupLog.nas_id == payload.nas_id,
                BackupLog.job_name == payload.job_name,
                BackupLog.snapshot_id == payload.snapshot_id,
            )
        )
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return LogIngestResponse(
                log_id=existing.id,
                received_at=existing.created_at,
                status=existing.status,
                created=False,
            )

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
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request may win after the pre-insert lookup. The unique
        # constraint is the final guard; resolve that race as a normal retry.
        db.rollback()
        if payload.snapshot_id is None:
            raise
        existing = db.scalar(
            select(BackupLog).where(
                BackupLog.nas_id == payload.nas_id,
                BackupLog.job_name == payload.job_name,
                BackupLog.snapshot_id == payload.snapshot_id,
            )
        )
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        return LogIngestResponse(
            log_id=existing.id,
            received_at=existing.created_at,
            status=existing.status,
            created=False,
        )
    db.refresh(log)
    return LogIngestResponse(
        log_id=log.id,
        received_at=log.created_at,
        status=log.status,
        created=True,
    )


@router.get(
    "",
    response_model=PaginatedLogs,
    summary="List backup logs with filters",
)
def list_logs(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
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
    # Build a narrow WHERE clause only from filters the caller supplied.
    conditions = []
    if nas_id:
        conditions.append(BackupLog.nas_id == nas_id)
    if status_filter:
        conditions.append(BackupLog.status == status_filter.upper())
    if job_name:
        conditions.append(BackupLog.job_name.ilike(f"%{job_name}%"))
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


@router.get(
    "/{log_id}",
    response_model=LogDetail,
    summary="Get backup log detail",
)
def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_operator_or_admin),
) -> LogDetail:
    """Get a single backup log's full detail. Role: admin/operator."""
    log = db.get(BackupLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return LogDetail.model_validate(log)


@router.patch(
    "/{log_id}/acknowledge",
    response_model=LogDetail,
    summary="Acknowledge a failed backup log",
)
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
    # SUCCESS logs do not enter the review workflow.
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


@router.delete(
    "/bulk",
    response_model=BulkDeleteResponse,
    summary="Bulk delete backup logs (by period or selected IDs)",
)
def bulk_delete_logs(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin),
) -> BulkDeleteResponse:
    """Delete multiple backup logs at once. Admin only.

    Two modes (can be combined):
    - **By period**: provide ``date_from`` and/or ``date_to`` to delete all logs
      within that UTC date range.
    - **By IDs**: provide a list of ``log_ids`` to delete specific logs.

    At least one filter must be specified.
    """
    if not payload.log_ids and payload.date_from is None and payload.date_to is None:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one filter: log_ids, date_from, or date_to.",
        )

    # Backup logs receive explicit UTC datetimes, so the bounds are used as-is.
    conditions = build_bulk_delete_conditions(
        id_column=BackupLog.id,
        ids=payload.log_ids,
        date_column=BackupLog.created_at,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )

    rows = db.scalars(select(BackupLog).where(*conditions)).all()
    count = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return BulkDeleteResponse(deleted_count=count)
