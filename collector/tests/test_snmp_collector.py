"""Smoke tests for SNMP exporter metric normalization."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import snmp_collector as snmp  # noqa: E402


class SnmpCollectorTest(unittest.TestCase):
    def test_synology_standard_mibs_are_normalized(self):
        """Synology should use UCD-SNMP, HOST-RESOURCES, and sysUpTime."""
        text = """
        ssCpuIdle 80
        memTotalReal 1000
        memAvailReal 200
        memBuffer 100
        memCached 100
        hrStorageSize{hrStorageIndex="1",hrStorageDescr="/volume1"} 1000
        hrStorageUsed{hrStorageIndex="1",hrStorageDescr="/volume1"} 650
        hrStorageAllocationUnits{hrStorageIndex="1",hrStorageDescr="/volume1"} 4096
        sysUpTime 1234500
        """
        metrics = snmp._parse_prometheus_text(text)
        normalized = {item["name"]: item["value"] for item in snmp._collect_normalized(metrics, "synology")}

        self.assertEqual(normalized["cpu_usage"], 20.0)
        self.assertEqual(normalized["ram_used_pct"], 60.0)
        self.assertEqual(normalized["disk_used_pct"], 65.0)
        self.assertEqual(normalized["system_uptime"], 12345)

    def test_wd_display_string_metrics_are_normalized(self):
        """WD DisplayString labels should still become numeric dashboard metrics."""
        text = """
        mycloudpr4100VolumeSize{mycloudpr4100VolumeNum="1",mycloudpr4100VolumeSize="1000"} 1
        mycloudpr4100VolumeFreeSpace{mycloudpr4100VolumeNum="1",mycloudpr4100VolumeFreeSpace="250"} 1
        sysUpTime 10000
        """
        metrics = snmp._parse_prometheus_text(text)
        normalized = {item["name"]: item["value"] for item in snmp._collect_normalized(metrics, "wd")}

        self.assertEqual(normalized["disk_used_pct"], 75.0)
        self.assertEqual(normalized["system_uptime"], 100)

    def test_host_uptime_is_preferred_over_snmp_agent_uptime(self):
        """System uptime should use host uptime, not the SNMP agent uptime."""
        text = """
        sysUpTime 77040000
        hrSystemUptime 750960000
        """
        metrics = snmp._parse_prometheus_text(text)
        normalized = {item["name"]: item for item in snmp._collect_normalized(metrics, "generic")}

        self.assertEqual(normalized["system_uptime"]["value"], 7509600)

    def test_scientific_notation_uptime_is_normalized(self):
        """Prometheus scientific notation TimeTicks should become seconds."""
        text = """
        sysUpTime 7.9570907e+07
        """
        metrics = snmp._parse_prometheus_text(text)
        normalized = {item["name"]: item for item in snmp._collect_normalized(metrics, "generic")}

        self.assertEqual(normalized["system_uptime"]["value"], 795709)

    def test_missing_uptime_is_reported_as_unavailable(self):
        """Missing uptime should not look like a real zero-minute uptime."""
        metrics = snmp._parse_prometheus_text("ssCpuIdle 80")
        normalized = {item["name"]: item for item in snmp._collect_normalized(metrics, "generic")}

        self.assertNotIn("value", normalized["system_uptime"])
        self.assertEqual(normalized["system_uptime"]["text"], "N/A")

    def test_centralized_exporter_url_preserves_auth_query(self):
        """Base /snmp URL may already include auth; target/module are appended."""
        url = snmp._build_exporter_url(
            "192.168.24.5",
            "http://exporter:9116/snmp?auth=kkp_snmp_v2",
            "synology_nas",
            9116,
        )

        self.assertEqual(
            url,
            "http://exporter:9116/snmp?auth=kkp_snmp_v2&target=192.168.24.5&module=synology_nas",
        )


if __name__ == "__main__":
    unittest.main()
