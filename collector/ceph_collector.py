"""Ceph HTTP Metric Collector (Stub for real hardware)."""

import random

def get_mock_ceph_metrics(cluster_id: str) -> list[dict]:
    """Generate fake mock metrics for a Ceph cluster."""
    storage_total = 3000000000000  # ~3TB
    used_pct = round(random.uniform(40.0, 75.0), 1)
    storage_used = int(storage_total * (used_pct / 100))
    
    health = random.choices(["HEALTH_OK", "HEALTH_WARN"], weights=[90, 10])[0]
    osd_up = random.choices([3, 2], weights=[95, 5])[0]
    
    return [
        {"name": "health_status", "text": health, "unit": "status"},
        {"name": "osd_up", "value": osd_up, "unit": "count"},
        {"name": "osd_total", "value": 3, "unit": "count"},
        {"name": "storage_used_pct", "value": used_pct, "unit": "%"},
        {"name": "storage_used_bytes", "value": storage_used, "unit": "bytes"},
        {"name": "storage_total_bytes", "value": storage_total, "unit": "bytes"},
        {"name": "read_iops", "value": random.randint(0, 150), "unit": "iops"},
        {"name": "write_iops", "value": random.randint(0, 200), "unit": "iops"},
        {"name": "ceph_reachable", "value": 1, "unit": "bool"},
    ]

import httpx
import logging
from snmp_collector import _parse_prometheus_text, _get_single

logger = logging.getLogger(__name__)

def get_prometheus_ceph_metrics(metrics_url: str) -> list[dict]:
    """Scrape real Ceph Manager metrics from the Prometheus exporter."""
    try:
        resp = httpx.get(metrics_url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to scrape Ceph metrics at {metrics_url}: {e}")
        return [
            {"name": "health_status", "text": "UNKNOWN", "unit": "status"},
            {"name": "osd_up", "value": 0, "unit": "count"},
            {"name": "osd_total", "value": 0, "unit": "count"},
            {"name": "storage_used_pct", "value": 0, "unit": "%"},
            {"name": "storage_used_bytes", "value": 0, "unit": "bytes"},
            {"name": "storage_total_bytes", "value": 0, "unit": "bytes"},
            {"name": "read_iops", "value": 0, "unit": "iops"},
            {"name": "write_iops", "value": 0, "unit": "iops"},
            {"name": "ceph_reachable", "value": 0, "unit": "bool"},
        ]

    metrics = _parse_prometheus_text(resp.text)
    result = []

    # Health status (0=OK, 1=WARN, 2=ERR)
    health_val = _get_single(metrics, ("ceph_health_status",), 2.0)
    if health_val == 0.0:
        health_str = "HEALTH_OK"
    elif health_val == 1.0:
        health_str = "HEALTH_WARN"
    else:
        health_str = "HEALTH_ERR"
    result.append({"name": "health_status", "text": health_str, "unit": "status"})

    # Health detail
    details = metrics.get("ceph_health_detail", [])
    active_alerts = [labels.get("name", "Unknown") for labels, val in details if val > 0]
    detail_str = ", ".join(active_alerts) if active_alerts else "None"
    result.append({"name": "health_detail", "text": detail_str, "unit": "info"})

    # OSD up and in (total)
    osd_up_list = metrics.get("ceph_osd_up", [])
    osd_in_list = metrics.get("ceph_osd_in", [])
    osd_up = sum([val for labels, val in osd_up_list])
    osd_total = sum([val for labels, val in osd_in_list])
    result.append({"name": "osd_up", "value": int(osd_up), "unit": "count"})
    result.append({"name": "osd_total", "value": int(osd_total), "unit": "count"})

    # Storage usage
    total_bytes = _get_single(metrics, ("ceph_cluster_total_bytes",), 0)
    used_bytes = _get_single(metrics, ("ceph_cluster_total_used_bytes",), 0)
    result.append({"name": "storage_total_bytes", "value": total_bytes, "unit": "bytes"})
    result.append({"name": "storage_used_bytes", "value": used_bytes, "unit": "bytes"})

    used_pct = 0.0
    if total_bytes > 0:
        used_pct = round((used_bytes / total_bytes) * 100, 2)
    result.append({"name": "storage_used_pct", "value": used_pct, "unit": "%"})

    # IOPS (Metrics are counters, we cannot calculate current IOPS without state)
    # So we report 0 here. True IOPS requires a time-series DB like Prometheus itself.
    result.append({"name": "read_iops", "value": 0, "unit": "iops"})
    result.append({"name": "write_iops", "value": 0, "unit": "iops"})

    # Reachability
    result.append({"name": "ceph_reachable", "value": 1, "unit": "bool"})

    return result
