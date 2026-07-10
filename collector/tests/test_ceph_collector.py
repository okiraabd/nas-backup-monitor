"""Tests for Ceph Prometheus metric normalization."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ceph_collector as ceph  # noqa: E402


class CephCollectorTest(unittest.TestCase):
    def test_health_ok_and_storage_values_are_parsed(self):
        """Ceph health/status gauges should become dashboard-ready metrics."""

        class Response:
            text = """
            ceph_health_status 0.0
            ceph_cluster_total_bytes 1000
            ceph_cluster_total_used_bytes 250
            ceph_osd_up{ceph_daemon="osd.0"} 1
            ceph_osd_up{ceph_daemon="osd.1"} 1
            ceph_osd_in{ceph_daemon="osd.0"} 1
            ceph_osd_in{ceph_daemon="osd.1"} 1
            """

            def raise_for_status(self):
                return None

        with patch("httpx.get", return_value=Response()):
            metrics = ceph.get_prometheus_ceph_metrics("http://ceph.example/metrics")

        normalized = {item["name"]: item for item in metrics}

        self.assertEqual(normalized["health_status"]["text"], "HEALTH_OK")
        self.assertEqual(normalized["storage_total_bytes"]["value"], 1000.0)
        self.assertEqual(normalized["storage_used_bytes"]["value"], 250.0)
        self.assertEqual(normalized["storage_used_pct"]["value"], 25.0)
        self.assertEqual(normalized["osd_up"]["value"], 2)
        self.assertEqual(normalized["osd_total"]["value"], 2)
        self.assertEqual(normalized["ceph_reachable"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
