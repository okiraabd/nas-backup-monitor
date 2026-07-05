"""Report endpoint tests."""
from datetime import date


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
