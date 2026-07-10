"""Backup logs endpoint tests."""
from datetime import datetime, timezone


class TestLogIngest:
    def test_service_ingest_success(self, client, service_headers):
        payload = {
            "nas_id": "wd-pr4100",
            "job_name": "backup-test",
            "source_path": "/TEST",
            "source_ip": "192.168.1.11",
            "destination_target": "Ceph S3",
            "backup_engine": "kopia",
            "status": "SUCCESS",
            "snapshot_id": "abc123",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 10,
            "total_size_bytes": 1000,
            "total_files": 5,
            "message": "Test backup",
        }
        resp = client.post("/api/logs/ingest", json=payload, headers=service_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["created"] is True
        assert "log_id" in data

    def test_retry_same_snapshot_is_idempotent(self, client, service_headers):
        payload = {
            "nas_id": "wd-pr4100",
            "job_name": "backup-idempotency-test",
            "status": "SUCCESS",
            "snapshot_id": "snapshot-idempotency-001",
        }

        first = client.post("/api/logs/ingest", json=payload, headers=service_headers)
        retry = client.post("/api/logs/ingest", json=payload, headers=service_headers)

        assert first.status_code == 201
        assert first.json()["created"] is True
        assert retry.status_code == 200
        assert retry.json()["created"] is False
        assert retry.json()["log_id"] == first.json()["log_id"]

    def test_same_snapshot_id_is_allowed_for_different_job(self, client, service_headers):
        base = {
            "nas_id": "wd-pr4100",
            "status": "SUCCESS",
            "snapshot_id": "shared-snapshot-id",
        }
        first = client.post(
            "/api/logs/ingest",
            json={**base, "job_name": "backup-job-a"},
            headers=service_headers,
        )
        second = client.post(
            "/api/logs/ingest",
            json={**base, "job_name": "backup-job-b"},
            headers=service_headers,
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["log_id"] != second.json()["log_id"]

    def test_logs_without_snapshot_id_remain_separate_events(self, client, service_headers):
        payload = {
            "nas_id": "wd-pr4100",
            "job_name": "backup-pre-snapshot-failure",
            "status": "FAILED",
            "message": "Repository could not be opened",
        }

        first = client.post("/api/logs/ingest", json=payload, headers=service_headers)
        second = client.post("/api/logs/ingest", json=payload, headers=service_headers)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["log_id"] != second.json()["log_id"]

    def test_admin_cannot_ingest(self, client, admin_headers):
        payload = {
            "nas_id": "test",
            "job_name": "test",
            "status": "SUCCESS",
        }
        resp = client.post("/api/logs/ingest", json=payload, headers=admin_headers)
        assert resp.status_code == 403

    def test_invalid_status_422(self, client, service_headers):
        payload = {
            "nas_id": "test",
            "job_name": "test",
            "status": "INVALID_STATUS",
        }
        resp = client.post("/api/logs/ingest", json=payload, headers=service_headers)
        assert resp.status_code == 422

    def test_negative_counts_rejected(self, client, service_headers):
        payload = {
            "nas_id": "wd-pr4100",
            "job_name": "backup-negative-duration",
            "status": "FAILED",
            "duration_seconds": -1,
        }
        resp = client.post("/api/logs/ingest", json=payload, headers=service_headers)
        assert resp.status_code == 422

    def test_blank_snapshot_id_is_treated_as_missing(self, client, service_headers):
        payload = {
            "nas_id": "wd-pr4100",
            "job_name": "backup-blank-snapshot-id",
            "status": "FAILED",
            "snapshot_id": "   ",
            "message": "pre-snapshot failure",
        }

        first = client.post("/api/logs/ingest", json=payload, headers=service_headers)
        second = client.post("/api/logs/ingest", json=payload, headers=service_headers)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["log_id"] != second.json()["log_id"]

    def test_naive_timestamp_rejected(self, client, service_headers):
        payload = {
            "nas_id": "wd-pr4100",
            "job_name": "backup-naive-time",
            "status": "SUCCESS",
            "started_at": "2026-07-10T10:00:00",
        }
        resp = client.post("/api/logs/ingest", json=payload, headers=service_headers)
        assert resp.status_code == 422

    def test_ended_before_started_rejected(self, client, service_headers):
        payload = {
            "nas_id": "wd-pr4100",
            "job_name": "backup-invalid-time-range",
            "status": "FAILED",
            "started_at": "2026-07-10T10:00:00+00:00",
            "ended_at": "2026-07-10T09:59:00+00:00",
        }
        resp = client.post("/api/logs/ingest", json=payload, headers=service_headers)
        assert resp.status_code == 422


class TestLogList:
    def test_admin_list_logs(self, client, admin_headers):
        resp = client.get("/api/logs", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_service_cannot_list_logs(self, client, service_headers):
        resp = client.get("/api/logs", headers=service_headers)
        assert resp.status_code == 403

    def test_filter_by_status(self, client, admin_headers):
        resp = client.get("/api/logs?status=FAILED", headers=admin_headers)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "FAILED"


class TestLogDetail:
    def test_get_log_detail(self, client, admin_headers):
        # First get the list to find an ID
        logs = client.get("/api/logs", headers=admin_headers).json()
        if logs["items"]:
            log_id = logs["items"][0]["id"]
            resp = client.get(f"/api/logs/{log_id}", headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["id"] == log_id

    def test_log_not_found(self, client, admin_headers):
        resp = client.get("/api/logs/99999", headers=admin_headers)
        assert resp.status_code == 404


class TestAcknowledge:
    def test_acknowledge_failed_log(self, client, admin_headers):
        # Find a FAILED log
        logs = client.get("/api/logs?status=FAILED", headers=admin_headers).json()
        failed = [l for l in logs["items"] if not l["acknowledged"]]
        if failed:
            log_id = failed[0]["id"]
            resp = client.patch(
                f"/api/logs/{log_id}/acknowledge",
                json={"remark": "Checked, network issue resolved."},
                headers=admin_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["acknowledged"] is True
