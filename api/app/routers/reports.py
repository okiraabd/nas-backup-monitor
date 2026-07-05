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
from app.schemas.report import ReportGenerate, ReportOut
from app.services.report_service import generate_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportOut])
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> list[Report]:
    """List generated reports (newest first). Role: admin."""
    return db.scalars(select(Report).order_by(Report.generated_at.desc())).all()


@router.post("/generate", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate(
    payload: ReportGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> Report:
    """Generate a PDF report for the given period. Role: admin."""
    return generate_report(
        db,
        date_from=payload.date_from,
        date_to=payload.date_to,
        nas_id=payload.nas_id,
        custom_name=payload.custom_name,
        generated_by=current_user,
    )


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator_or_admin),
) -> FileResponse:
    """Download a report's PDF file. Role: admin."""
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


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
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
