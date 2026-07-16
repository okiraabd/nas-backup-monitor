"""Report endpoint tests."""
from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.services.pdf_service import build_report_pdf


def test_failed_backup_table_handles_long_special_remark(tmp_path):
    output = tmp_path / "failed-backup-report.pdf"
    failed_log = SimpleNamespace(
        id=42,
        nas_id="synology-ds1522",
        job_name="backup-finance-and-operational-documents",
        status="FAILED",
        acknowledged=True,
        remark="Investigated <storage> & network path. " * 40,
        message=None,
        created_at=datetime(2026, 7, 16, 4, 8, tzinfo=timezone.utc),
    )

    build_report_pdf(
        str(output),
        date_from=date(2026, 7, 16),
        date_to=date(2026, 7, 16),
        nas_filter=None,
        logs=[failed_log],
        monitoring=[],
        generated_by_name="Administrator",
        activity_days=[],
    )

    assert output.exists()
    assert output.stat().st_size > 0


class TestReports:
    def test_generate_report(self, client, admin_headers):
        payload = {
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "nas_id": None,
        }
        resp = client.post("/api/reports/generate", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["filename"].endswith(".pdf")

    def test_list_reports(self, client, admin_headers):
        resp = client.get("/api/reports", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_download_report(self, client, admin_headers):
        # Generate first
        gen = client.post(
            "/api/reports/generate",
            json={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=admin_headers,
        )
        if gen.status_code == 201:
            report_id = gen.json()["id"]
            resp = client.get(f"/api/reports/{report_id}/download", headers=admin_headers)
            assert resp.status_code == 200
            assert resp.headers.get("content-type", "").startswith("application/pdf")

    def test_delete_report(self, client, admin_headers):
        # Generate, then delete
        gen = client.post(
            "/api/reports/generate",
            json={"date_from": "2026-06-01", "date_to": "2026-06-30"},
            headers=admin_headers,
        )
        if gen.status_code == 201:
            report_id = gen.json()["id"]
            resp = client.delete(f"/api/reports/{report_id}", headers=admin_headers)
            assert resp.status_code == 204

    def test_service_cannot_generate(self, client, service_headers):
        resp = client.post(
            "/api/reports/generate",
            json={"date_from": "2026-01-01", "date_to": "2026-12-31"},
            headers=service_headers,
        )
        assert resp.status_code == 403
