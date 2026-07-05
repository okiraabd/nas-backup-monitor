"""Report service — gather data, render PDF, persist metadata."""
import os
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.backup_log import BackupLog
from app.models.metric import SOURCE_CEPH, SOURCE_NAS
from app.models.report import Report
from app.models.user import User
from app.services import monitor_service
from app.services.pdf_service import build_report_pdf


def generate_report(
    db: Session,
    *,
    date_from: date,
    date_to: date,
    nas_id: str | None,
    custom_name: str | None = None,
    generated_by: User,
) -> Report:
    """Collect logs + monitoring, render a PDF, store the file and metadata."""
    # Inclusive day range: [date_from 00:00, date_to 23:59:59].
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to, time.max, tzinfo=timezone.utc)

    conditions = [BackupLog.created_at >= start, BackupLog.created_at <= end]
    if nas_id:
        conditions.append(BackupLog.nas_id == nas_id)
    logs = db.scalars(
        select(BackupLog).where(*conditions).order_by(BackupLog.created_at.desc())
    ).all()

    # Latest monitoring snapshot for all sources.
    monitoring = []
    for sid in monitor_service.list_source_ids(db, SOURCE_NAS):
        snap = monitor_service.latest_snapshot(db, SOURCE_NAS, sid)
        if snap:
            monitoring.append(snap)
    for sid in monitor_service.list_source_ids(db, SOURCE_CEPH):
        snap = monitor_service.latest_snapshot(db, SOURCE_CEPH, sid)
        if snap:
            monitoring.append(snap)

    import re
    os.makedirs(settings.reports_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if custom_name:
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', custom_name)
        filename = f"{safe_name}_{stamp}.pdf"
    else:
        suffix = f"_{nas_id}" if nas_id else ""
        filename = f"backup_report_{date_from.isoformat()}_{date_to.isoformat()}{suffix}_{stamp}.pdf"
    file_path = os.path.join(settings.reports_dir, filename)

    build_report_pdf(
        file_path,
        date_from=date_from,
        date_to=date_to,
        nas_filter=nas_id,
        logs=logs,
        monitoring=monitoring,
        generated_by_name=generated_by.display_name,
    )

    size = os.path.getsize(file_path) if os.path.exists(file_path) else None
    report = Report(
        filename=filename,
        date_from=date_from,
        date_to=date_to,
        nas_filter=nas_id,
        generated_by=generated_by.id,
        file_size_bytes=size,
        file_path=file_path,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
