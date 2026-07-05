"""SNMP Metric Collector — scrapes Prometheus SNMP Exporter /metrics endpoints."""

import random
import logging
import httpx

logger = logging.getLogger(__name__)


def get_mock_nas_metrics(nas_id: str) -> list[dict]:
    """Generate fake mock NAS metrics for testing/demo."""
    return [
        {"name": "cpu_usage", "value": round(random.uniform(5.0, 85.0), 1), "unit": "%"},
        {"name": "ram_used_pct", "value": round(random.uniform(20.0, 95.0), 1), "unit": "%"},
        {"name": "disk_used_pct", "value": round(random.uniform(40.0, 80.0), 1), "unit": "%"},
        {"name": "temperature", "value": random.randint(35, 55), "unit": "C"},
        {"name": "system_uptime", "value": random.randint(100000, 5000000), "unit": "seconds"},
        {"name": "snmp_reachable", "value": 1, "unit": "bool"},
    ]


# ---------------------------------------------------------------------------
# Internal helpers for parsing Prometheus text exposition format
# ---------------------------------------------------------------------------

def _parse_prometheus_text(text: str) -> dict[str, list[tuple[dict, float]]]:
    """Parse Prometheus text format into {metric_name: [(labels_dict, value), ...]}."""
    result: dict[str, list[tuple[dict, float]]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # metric_name{label1="v1",label2="v2"} value
        # metric_name value
        try:
            if "{" in line:
                name_part, rest = line.split("{", 1)
                labels_part, value_part = rest.rsplit("}", 1)
                labels = _parse_labels(labels_part)
                value = float(value_part.strip())
            else:
                parts = line.split()
                name_part = parts[0]
                labels = {}
                value = float(parts[1])
            result.setdefault(name_part, []).append((labels, value))
        except (ValueError, IndexError):
            continue
    return result


def _parse_labels(label_str: str) -> dict:
    """Parse 'key="value",key2="value2"' into a dict."""
    labels = {}
    if not label_str:
        return labels
    # Simple state-machine parser for quoted values
    i = 0
    while i < len(label_str):
        eq = label_str.find("=", i)
        if eq == -1:
            break
        key = label_str[i:eq].strip()
        # Find quoted value
        q1 = label_str.find('"', eq)
        if q1 == -1:
            break
        q2 = label_str.find('"', q1 + 1)
        if q2 == -1:
            break
        val = label_str[q1 + 1:q2]
        labels[key] = val
        # Skip to next entry (past the comma)
        i = q2 + 1
        if i < len(label_str) and label_str[i] == ",":
            i += 1
    return labels


def _get_single(metrics: dict, name: str, default=None) -> float | None:
    """Get a single scalar metric value (first match, no label filter)."""
    entries = metrics.get(name, [])
    if entries:
        return entries[0][1]
    return default


def _get_by_label(metrics: dict, name: str, label_key: str, label_val: str, default=None):
    """Get metric value filtered by a specific label."""
    for labels, value in metrics.get(name, []):
        if labels.get(label_key) == label_val:
            return value
    return default


# ---------------------------------------------------------------------------
# Synology NAS — rich SNMP MIBs
# ---------------------------------------------------------------------------

def _collect_synology(nas_id: str, metrics: dict) -> list[dict]:
    """Map Synology SNMP exporter metrics to our API format."""
    result = []

    # CPU usage: prefer (100 - ssCpuIdle) for accuracy, fallback to user + system
    cpu_idle = _get_single(metrics, "ssCpuIdle")
    if cpu_idle is not None:
        cpu_usage = max(0, 100 - cpu_idle)
    else:
        cpu_user = _get_single(metrics, "ssCpuUser", 0)
        cpu_system = _get_single(metrics, "ssCpuSystem", 0)
        cpu_usage = cpu_user + cpu_system
    result.append({"name": "cpu_usage", "value": round(cpu_usage, 1), "unit": "%"})

    # RAM: memTotalReal, memAvailReal, memBuffer, memCached (all in KB)
    mem_total = _get_single(metrics, "memTotalReal")
    mem_avail = _get_single(metrics, "memAvailReal", 0)
    mem_buffer = _get_single(metrics, "memBuffer", 0)
    mem_cached = _get_single(metrics, "memCached", 0)
    if mem_total and mem_total > 0:
        # Effective free = avail + buffer + cached
        mem_used = mem_total - (mem_avail + mem_buffer + mem_cached)
        ram_pct = round((mem_used / mem_total) * 100, 1)
        result.append({"name": "ram_used_pct", "value": max(0, ram_pct), "unit": "%"})
    else:
        result.append({"name": "ram_used_pct", "value": 0, "unit": "%"})

    # Disk / RAID: use the largest Volume for disk_used_pct
    raid_total_entries = metrics.get("raidTotalSize", [])
    raid_free_entries = metrics.get("raidFreeSize", [])
    best_total = 0
    best_free = 0
    for labels, total_val in raid_total_entries:
        raid_name = labels.get("raidName", "")
        # Skip "Storage Pool", use actual Volumes
        if "Volume" not in raid_name:
            continue
        free_val = _get_by_label(metrics, "raidFreeSize", "raidName", raid_name, 0)
        if total_val > best_total:
            best_total = total_val
            best_free = free_val

    if best_total > 0:
        used_pct = round(((best_total - best_free) / best_total) * 100, 1)
        result.append({"name": "disk_used_pct", "value": used_pct, "unit": "%"})
    else:
        result.append({"name": "disk_used_pct", "value": 0, "unit": "%"})

    # Temperature (system body)
    temp = _get_single(metrics, "temperature", 0)
    result.append({"name": "temperature", "value": int(temp), "unit": "C"})

    # Uptime — not available from Synology MIB in this exporter config, use 0
    result.append({"name": "system_uptime", "value": 0, "unit": "seconds"})

    # Reachable
    result.append({"name": "snmp_reachable", "value": 1, "unit": "bool"})

    return result


# ---------------------------------------------------------------------------
# WD NAS — only IF-MIB (network) + sysUpTime
# ---------------------------------------------------------------------------

def _collect_wd(nas_id: str, metrics: dict) -> list[dict]:
    """Map WD SNMP exporter metrics to our API format.
    
    WD only exposes IF-MIB (network interfaces) and sysUpTime.
    CPU/RAM/Disk are not available via SNMP on this device, so we report 0.
    """
    result = []

    # CPU / RAM / Disk: not available from WD SNMP exporter
    result.append({"name": "cpu_usage", "value": 0, "unit": "%"})
    result.append({"name": "ram_used_pct", "value": 0, "unit": "%"})
    result.append({"name": "disk_used_pct", "value": 0, "unit": "%"})

    # Temperature: not available
    result.append({"name": "temperature", "value": 0, "unit": "C"})

    # Uptime: sysUpTime is in hundredths of a second
    sys_uptime_hs = _get_single(metrics, "sysUpTime", 0)
    uptime_seconds = int(sys_uptime_hs / 100)
    result.append({"name": "system_uptime", "value": uptime_seconds, "unit": "seconds"})

    # Reachable
    result.append({"name": "snmp_reachable", "value": 1, "unit": "bool"})

    return result


# ---------------------------------------------------------------------------
# Public API: collect real metrics
# ---------------------------------------------------------------------------

def get_snmp_nas_metrics(nas_id: str, ip: str, exporter_port: int = 9116) -> list[dict]:
    """Scrape Prometheus SNMP exporter at http://{ip}:{port}/metrics and
    return metrics in our API-compatible format.
    
    Automatically detects whether the target is a Synology (has ssCpuIdle)
    or WD (only has IF-MIB) and maps accordingly.
    """
    url = f"http://{ip}:{exporter_port}/metrics"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to scrape SNMP exporter at {url}: {e}")
        return [
            {"name": "cpu_usage", "value": 0, "unit": "%"},
            {"name": "ram_used_pct", "value": 0, "unit": "%"},
            {"name": "disk_used_pct", "value": 0, "unit": "%"},
            {"name": "temperature", "value": 0, "unit": "C"},
            {"name": "system_uptime", "value": 0, "unit": "seconds"},
            {"name": "snmp_reachable", "value": 0, "unit": "bool"},
        ]

    metrics = _parse_prometheus_text(resp.text)

    # Auto-detect device type based on available metrics
    # UCD-SNMP-MIB contains memTotalReal and ssCpuIdle, which is standard for Linux (Synology & WD)
    has_ucd_snmp = "ssCpuIdle" in metrics or "memTotalReal" in metrics
    
    if has_ucd_snmp:
        logger.info(f"Detected UCD-SNMP (CPU/RAM) metrics for {nas_id}")
        return _collect_synology(nas_id, metrics)
    else:
        logger.info(f"Detected Generic (Network Only) SNMP data for {nas_id}")
        return _collect_wd(nas_id, metrics)
