"""PDF generation using ReportLab — redesigned with SLA focus."""
from datetime import date, datetime, timezone
from typing import Any

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.timezone import format_local_datetime

# --- Brand colours ---
COLOR_PRIMARY = colors.HexColor("#1e40af")   # blue-800
COLOR_SUCCESS = colors.HexColor("#16a34a")   # green-600
COLOR_DANGER  = colors.HexColor("#dc2626")   # red-600
COLOR_WARN    = colors.HexColor("#d97706")   # amber-600
COLOR_HEADER  = colors.HexColor("#1e293b")   # slate-800
COLOR_ROW_ALT = colors.HexColor("#f1f5f9")   # slate-100
COLOR_MUTED   = colors.HexColor("#64748b")   # slate-500


def _fmt_bytes(n: int | None) -> str:
    if not n:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for u in units:
        if size < 1024 or u == units[-1]:
            return f"{size:.1f} {u}"
        size /= 1024
    return f"{n}"


def _sla_color(actual: float, target: float) -> Any:
    if actual >= target:
        return COLOR_SUCCESS
    if actual >= target - 1:
        return COLOR_WARN
    return COLOR_DANGER


def _build_sla_pie(success: int, failed: int) -> Drawing:
    """Return a small Pie chart Drawing for success/failure ratio."""
    d = Drawing(160, 120)
    pie = Pie()
    pie.x = 30
    pie.y = 10
    pie.width = 100
    pie.height = 100
    total = success + failed or 1
    pie.data = [success, failed] if failed > 0 else [success, 0.001]
    pie.labels = [f"Success\n{success/total*100:.1f}%", f"Failed\n{failed/total*100:.1f}%"]
    pie.slices[0].fillColor = COLOR_SUCCESS
    pie.slices[1].fillColor = COLOR_DANGER
    pie.slices.strokeWidth = 0.5
    pie.slices.strokeColor = colors.white
    pie.simpleLabels = False
    pie.sideLabels = True
    d.add(pie)
    return d


def _build_daily_bar(days: list[dict]) -> Drawing:
    """Return a simple VerticalBarChart for daily success/failed trend."""
    if not days:
        return Drawing(400, 150)
    d = Drawing(400, 160)
    bc = VerticalBarChart()
    bc.x = 40
    bc.y = 20
    bc.height = 120
    bc.width = 340
    bc.data = [
        [row.get("success", 0) for row in days],
        [row.get("failed",  0) for row in days],
    ]
    bc.categoryAxis.categoryNames = [str(row.get("date", ""))[-5:] for row in days]
    
    num_days = len(days)
    if num_days <= 14:
        bc.categoryAxis.labels.fontSize = 7
        bc.categoryAxis.labels.angle = 30
        bc.categoryAxis.labels.dy = -8
        bc.groupSpacing = 4
    elif num_days <= 31:
        bc.categoryAxis.labels.fontSize = 5
        bc.categoryAxis.labels.angle = 90
        bc.categoryAxis.labels.dy = -15
        bc.groupSpacing = 2
    else:
        # Hide labels for very long periods (>31 days) to prevent overlapping black mess
        bc.categoryAxis.labels.fontSize = 0
        bc.groupSpacing = 1

    bc.bars[0].fillColor = COLOR_SUCCESS
    bc.bars[1].fillColor = COLOR_DANGER
    bc.valueAxis.labels.fontSize = 7
    d.add(bc)
    # Legend
    d.add(String(45, 155, "■ Success", fontSize=8, fillColor=COLOR_SUCCESS))
    d.add(String(115, 155, "■ Failed",  fontSize=8, fillColor=COLOR_DANGER))
    return d


def build_report_pdf(
    file_path: str,
    *,
    date_from: date,
    date_to: date,
    nas_filter: str | None,
    logs: list,
    monitoring: list,
    generated_by_name: str,
    sla_target: float = 99.5,
    activity_days: list[dict] | None = None,
) -> None:
    """Render a comprehensive SLA-focused backup report PDF to `file_path`."""
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=COLOR_HEADER,
        spaceAfter=4,
    )
    h2 = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=COLOR_PRIMARY,
        spaceBefore=10,
        spaceAfter=6,
    )
    h3 = ParagraphStyle(
        "SectionH3",
        parent=styles["Heading3"],
        fontSize=10,
        textColor=COLOR_HEADER,
        spaceBefore=8,
        spaceAfter=4,
    )
    normal = styles["Normal"]
    small  = ParagraphStyle("small", parent=normal, fontSize=8, textColor=COLOR_MUTED)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        title="Backup Monitoring SLA Report",
    )
    story: list = []

    # ─── Cover / Header ────────────────────────────────────────────────────
    story.append(Paragraph("Backup Monitoring Report", title_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY, spaceAfter=6))
    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>PT Lucky Mom Indonesia</b>", styles["Normal"]))
    story.append(Spacer(1, 6))

    meta_data = [
        ["Period", f"{date_from.isoformat()}  —  {date_to.isoformat()}"],
        ["NAS Filter", nas_filter or "All NAS Devices"],
        ["Generated by", generated_by_name],
        ["Generated at", f"{format_local_datetime(datetime.now(timezone.utc), '%Y-%m-%d %H:%M:%S')} WIB"],
    ]
    meta_table = Table(meta_data, colWidths=[38 * mm, 130 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_MUTED),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # ─── Executive Summary / SLA Dashboard ────────────────────────────────
    story.append(Paragraph("SLA Dashboard", h2))

    total   = len(logs)
    success = sum(1 for l in logs if l.status == "SUCCESS")
    failed  = sum(1 for l in logs if l.status == "FAILED")
    unack   = sum(1 for l in logs if l.status == "FAILED" and not l.acknowledged)
    actual_sla = (success / total * 100) if total > 0 else 100.0
    sla_met = actual_sla >= sla_target

    sla_color = _sla_color(actual_sla, sla_target)

    # Summary metrics row
    summary_data = [
        ["Total Backups", "Success", "Failed", "Unacknowledged", "Success Rate"],
        [
            str(total),
            str(success),
            str(failed),
            str(unack),
            f"{actual_sla:.2f}%",
        ],
    ]
    summary_table = Table(summary_data, colWidths=[35 * mm, 30 * mm, 30 * mm, 45 * mm, 30 * mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("FONTNAME",   (0, 1), (-1, 1), "Helvetica-Bold"),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # Visualisasi: Pie chart + bar chart (Sequential)
    if total > 0:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Overall Success Ratio</b>", h3))
        story.append(Spacer(1, 4))
        pie_drawing = _build_sla_pie(success, failed)
        pie_table = Table([[pie_drawing]])
        pie_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(pie_table)
        story.append(Spacer(1, 20))

        story.append(Paragraph("<b>Backup Job Trends (Selected Period)</b>", h3))
        story.append(Spacer(1, 4))
        bar_drawing = _build_daily_bar(activity_days or [])
        bar_table = Table([[bar_drawing]])
        bar_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(bar_table)
        story.append(Spacer(1, 16))

    # ─── Conclusion ───────────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=COLOR_PRIMARY, spaceBefore=8))
    conclusion = (
        f"<b>Conclusion:</b> For this period, the system achieved a backup success rate of <b>{actual_sla:.2f}%</b>. "
        f"A total of {total} backup jobs were executed — {success} succeeded, {failed} failed "
        f"({unack} unacknowledged)."
    )
    if failed > 0:
        conclusion += " Please review the Failed Backups Appendix for details."
    story.append(Spacer(1, 6))
    story.append(Paragraph(conclusion, normal))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Report generated at {format_local_datetime(datetime.now(timezone.utc), '%Y-%m-%d %H:%M:%S')} WIB by {generated_by_name}.",
        small,
    ))

    # ─── Failed Backups Detail (Appendix) ─────────────────────────────────
    failed_logs = [l for l in logs if l.status == "FAILED"]
    if failed_logs:
        story.append(PageBreak())
        story.append(Paragraph("Failed Backups (Appendix)", h2))
        rows = [["ID", "NAS", "Job", "Ack", "Remark / Message"]]
        for l in failed_logs:
            note = l.remark or l.message or "-"
            rows.append([
                str(l.id),
                l.nas_id,
                l.job_name[:25],
                "Yes" if l.acknowledged else "No",
                note[:55],
            ])
        t = Table(rows, colWidths=[12 * mm, 28 * mm, 30 * mm, 14 * mm, 74 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7f1d1d")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("GRID",       (0, 0), (-1, -1), 0.4, colors.grey),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 14))

    doc.build(story)
