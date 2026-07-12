"""Reports router: list, generate (PDF), download, delete. Admin-only."""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_operator_or_admin
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportGenerate, ReportOut, ReportBulkDelete, BulkDeleteResponse
from app.services.report_service import generate_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "",
    response_model=list[ReportOut],
    summary="List generated reports",
)
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> list[Report]:
    """List generated reports (newest first). Role: admin/operator."""
    return db.scalars(select(Report).order_by(Report.generated_at.desc())).all()


@router.post(
    "/generate",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a PDF backup report",
)
def generate(
    payload: ReportGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> Report:
    """Generate a PDF report for the given period. Role: admin/operator."""
    return generate_report(
        db,
        date_from=payload.date_from,
        date_to=payload.date_to,
        nas_id=payload.nas_id,
        custom_name=payload.custom_name,
        generated_by=current_user,
        sla_target=payload.sla_target,
    )


@router.get(
    "/{report_id}/download",
    summary="Download a report PDF",
)
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> FileResponse:
    """Download a report's PDF file. Role: admin/operator."""
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=410, detail="Report file no longer available")
    return FileResponse(
        report.file_path,
        media_type="application/pdf",
        filename=report.filename,
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report and its file",
)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    """Delete a report record and its file. Role: admin."""
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    # Remove file best-effort, then the DB row.
    try:
        if os.path.exists(report.file_path):
            os.remove(report.file_path)
    except OSError:
        pass
    db.delete(report)
    db.commit()

@router.delete(
    "",
    status_code=status.HTTP_200_OK,
    response_model=BulkDeleteResponse,
    summary="Bulk delete reports by IDs or period",
)
def bulk_delete_reports(
    payload: ReportBulkDelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> BulkDeleteResponse:
    """Delete multiple reports and their files. Role: admin."""
    if not payload.report_ids and payload.date_from is None and payload.date_to is None:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one filter: report_ids, date_from, or date_to.",
        )

    conditions = []

    if payload.report_ids:
        conditions.append(Report.id.in_(payload.report_ids))

    date_conditions = []
    from datetime import datetime, time
    from zoneinfo import ZoneInfo
    from app.config import settings
    tz = ZoneInfo(settings.app_timezone)

    if payload.date_from:
        start_of_day = datetime.combine(payload.date_from, time.min, tzinfo=tz)
        date_conditions.append(Report.generated_at >= start_of_day)
    if payload.date_to:
        end_of_day = datetime.combine(payload.date_to, time.max, tzinfo=tz)
        date_conditions.append(Report.generated_at <= end_of_day)

    if date_conditions:
        from sqlalchemy import and_
        if payload.report_ids:
            from sqlalchemy import or_
            conditions = [or_(Report.id.in_(payload.report_ids), and_(*date_conditions))]
        else:
            conditions = date_conditions

    rows = db.scalars(select(Report).where(*conditions)).all()
    count = len(rows)
    for row in rows:
        try:
            if os.path.exists(row.file_path):
                os.remove(row.file_path)
        except OSError:
            pass
        db.delete(row)
    
    db.commit()
    return BulkDeleteResponse(deleted_count=count)
