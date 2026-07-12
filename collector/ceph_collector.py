"""Ceph HTTP metric collector for mock and Prometheus-backed Ceph data."""

import logging
import random

import httpx

from snmp_collector import _parse_prometheus_text

logger = logging.getLogger(__name__)


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
        {"name": "osd_in", "value": osd_up, "unit": "count"},
        {"name": "osd_total", "value": 3, "unit": "count"},
        {"name": "storage_used_pct", "value": used_pct, "unit": "%"},
        {"name": "storage_used_bytes", "value": storage_used, "unit": "bytes"},
        {"name": "storage_total_bytes", "value": storage_total, "unit": "bytes"},
        {"name": "ceph_reachable", "value": 1, "unit": "bool"},
    ]


def _get_metric_value(metrics: dict, name: str, default: float | None = None) -> float | None:
    """Return the first value for one Prometheus metric name."""
    series = metrics.get(name, [])
    if not series:
        return default
    return series[0][1]


def _count_unique_osd_daemons(metrics: dict, names: tuple[str, ...]) -> int:
    """Count unique ceph_daemon labels from the first available OSD metric."""
    daemons = set()
    for name in names:
        for labels, _value in metrics.get(name, []):
            daemon = labels.get("ceph_daemon")
            if daemon:
                daemons.add(daemon)
        if daemons:
            return len(daemons)
    return 0


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
            {"name": "osd_in", "value": 0, "unit": "count"},
            {"name": "osd_total", "value": 0, "unit": "count"},
            {"name": "storage_used_pct", "value": 0, "unit": "%"},
            {"name": "storage_used_bytes", "value": 0, "unit": "bytes"},
            {"name": "storage_total_bytes", "value": 0, "unit": "bytes"},
            {"name": "ceph_reachable", "value": 0, "unit": "bool"},
        ]

    metrics = _parse_prometheus_text(resp.text)
    result = []

    # Health status (0=OK, 1=WARN, 2=ERR)
    health_val = _get_metric_value(metrics, "ceph_health_status", 2.0)
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

    # OSD counts: osd_total needs a metric that still lists out/down OSDs.
    osd_up_list = metrics.get("ceph_osd_up", [])
    osd_in_list = metrics.get("ceph_osd_in", [])
    osd_up = sum(1 for _labels, val in osd_up_list if val > 0)
    osd_in = sum(1 for _labels, val in osd_in_list if val > 0)
    osd_total = _count_unique_osd_daemons(
        metrics,
        (
            "ceph_osd_apply_latency_ms",
            "ceph_osd_commit_latency_ms",
            "ceph_osd_up",
            "ceph_osd_in",
        ),
    )
    result.append({"name": "osd_up", "value": int(osd_up), "unit": "count"})
    result.append({"name": "osd_in", "value": int(osd_in), "unit": "count"})
    result.append({"name": "osd_total", "value": int(osd_total), "unit": "count"})

    # Storage usage
    total_bytes = _get_metric_value(metrics, "ceph_cluster_total_bytes", 0) or 0
    used_bytes = _get_metric_value(metrics, "ceph_cluster_total_used_bytes", 0) or 0
    result.append({"name": "storage_total_bytes", "value": total_bytes, "unit": "bytes"})
    result.append({"name": "storage_used_bytes", "value": used_bytes, "unit": "bytes"})

    used_pct = 0.0
    if total_bytes > 0:
        used_pct = round((used_bytes / total_bytes) * 100, 2)
    result.append({"name": "storage_used_pct", "value": used_pct, "unit": "%"})

    # Reachability
    result.append({"name": "ceph_reachable", "value": 1, "unit": "bool"})

    return result
