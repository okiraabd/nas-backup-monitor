"""Monitoring endpoint tests."""
from datetime import datetime, timezone


class TestMonitorIngest:
    def test_collector_ingest_nas_metrics(self, client, collector_headers):
        payload = {
            "source_type": "nas",
            "source_id": "synology-ds1522",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metrics": [
                {"name": "cpu_usage", "value": 25, "unit": "%"},
                {"name": "ram_used_pct", "value": 60, "unit": "%"},
            ],
        }
        resp = client.post("/api/monitor/ingest", json=payload, headers=collector_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_id"] == "synology-ds1522"
        assert data["stored_metrics"] == 2
        assert data["status"] == "accepted"

    def test_collector_ingest_ceph_metrics(self, client, collector_headers):
        payload = {
            "source_type": "ceph",
            "source_id": "ceph-cluster",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metrics": [
                {"name": "health_status", "text": "HEALTH_OK", "unit": "status"},
                {"name": "osd_up", "value": 3, "unit": "count"},
            ],
        }
        resp = client.post("/api/monitor/ingest", json=payload, headers=collector_headers)
        assert resp.status_code == 201

    def test_admin_cannot_ingest_metrics(self, client, admin_headers):
        payload = {
            "source_type": "nas",
            "source_id": "test",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metrics": [{"name": "cpu_usage", "value": 10, "unit": "%"}],
        }
        resp = client.post("/api/monitor/ingest", json=payload, headers=admin_headers)
        assert resp.status_code == 403

    def test_invalid_source_type(self, client, collector_headers):
        payload = {
            "source_type": "invalid",
            "source_id": "test",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metrics": [{"name": "x", "value": 1, "unit": "y"}],
        }
        resp = client.post("/api/monitor/ingest", json=payload, headers=collector_headers)
        assert resp.status_code == 422

    def test_metric_requires_value_or_text(self, client, collector_headers):
        payload = {
            "source_type": "nas",
            "source_id": "validation-test",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "metrics": [{"name": "cpu_usage", "unit": "%"}],
        }
        resp = client.post("/api/monitor/ingest", json=payload, headers=collector_headers)
        assert resp.status_code == 422

    def test_collected_at_must_be_timezone_aware(self, client, collector_headers):
        payload = {
            "source_type": "nas",
            "source_id": "validation-test",
            "collected_at": "2026-07-10T10:00:00",
            "metrics": [{"name": "cpu_usage", "value": 1, "unit": "%"}],
        }
        resp = client.post("/api/monitor/ingest", json=payload, headers=collector_headers)
        assert resp.status_code == 422


class TestMonitorRead:
    def test_monitor_summary(self, client, admin_headers):
        resp = client.get("/api/monitor/summary", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_nas" in data
        assert "ceph_status" in data

    def test_list_nas(self, client, admin_headers):
        resp = client.get("/api/monitor/nas", headers=admin_headers)
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_get_nas_detail(self, client, admin_headers):
        resp = client.get("/api/monitor/nas/synology-ds1522", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_id"] == "synology-ds1522"
        assert data["status"] in ("fresh", "stale", "offline")

    def test_nas_history(self, client, admin_headers):
        resp = client.get(
            "/api/monitor/nas/synology-ds1522/history?metric=cpu_usage",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["metric_name"] == "cpu_usage"

    def test_ceph_snapshot(self, client, admin_headers):
        resp = client.get("/api/monitor/ceph", headers=admin_headers)
        # May 404 if no ceph data in test seed, or 200
        assert resp.status_code in (200, 404)

    def test_collector_status(self, client, admin_headers):
        resp = client.get("/api/monitor/collector/status", headers=admin_headers)
        assert resp.status_code == 200

    def test_latest_snapshot_uses_latest_value_per_metric(self, client, collector_headers, admin_headers):
        source_id = "latest-snapshot-optimized"
        older = {
            "source_type": "nas",
            "source_id": source_id,
            "collected_at": "2026-07-10T00:00:00+00:00",
            "metrics": [{"name": "cpu_usage", "value": 10, "unit": "%"}],
        }
        newer = {
            "source_type": "nas",
            "source_id": source_id,
            "collected_at": "2026-07-10T00:05:00+00:00",
            "metrics": [{"name": "cpu_usage", "value": 42, "unit": "%"}],
        }

        assert client.post("/api/monitor/ingest", json=older, headers=collector_headers).status_code == 201
        assert client.post("/api/monitor/ingest", json=newer, headers=collector_headers).status_code == 201

        resp = client.get(f"/api/monitor/nas/{source_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["metrics"]["cpu_usage"]["value"] == 42.0

    def test_collector_run_report_validates_status(self, client, collector_headers):
        payload = {
            "started_at": "2026-07-10T00:00:00+00:00",
            "finished_at": "2026-07-10T00:01:00+00:00",
            "status": "UNKNOWN",
            "is_mock": False,
            "total_sources": 1,
            "success_sources": 1,
            "failed_sources": 0,
        }
        resp = client.post("/api/monitor/collector/run", json=payload, headers=collector_headers)
        assert resp.status_code == 422
