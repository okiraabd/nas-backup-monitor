"""Collect NAS metrics from Prometheus SNMP Exporter output.

The collector does not speak SNMP directly. It reads Prometheus text generated
by snmp_exporter, then normalizes the values expected by the dashboard.
"""

from __future__ import annotations

import logging
import random
import re
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

MetricSeries = dict[str, list[tuple[dict[str, str], float]]]

_STRICT_NUMBER = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:[A-Za-z%]+)?\s*$")


def get_mock_nas_metrics(nas_id: str) -> list[dict]:
    """Generate fake NAS metrics for demo/test mode."""
    return [
        {"name": "cpu_usage", "value": round(random.uniform(5.0, 85.0), 1), "unit": "%"},
        {"name": "ram_used_pct", "value": round(random.uniform(20.0, 95.0), 1), "unit": "%"},
        {"name": "disk_used_pct", "value": round(random.uniform(40.0, 80.0), 1), "unit": "%"},
        {"name": "temperature", "value": random.randint(35, 55), "unit": "C"},
        {"name": "system_uptime", "value": random.randint(100000, 5000000), "unit": "seconds"},
        {"name": "snmp_reachable", "value": 1, "unit": "bool"},
    ]


def _unreachable_metrics() -> list[dict]:
    """Return zeroed metrics when the exporter/NAS cannot be scraped."""
    return [
        {"name": "cpu_usage", "value": 0, "unit": "%"},
        {"name": "ram_used_pct", "value": 0, "unit": "%"},
        {"name": "disk_used_pct", "value": 0, "unit": "%"},
        {"name": "temperature", "value": 0, "unit": "C"},
        {"name": "system_uptime", "value": 0, "unit": "seconds"},
        {"name": "snmp_reachable", "value": 0, "unit": "bool"},
    ]


def _clamp_pct(value: float) -> float:
    """Keep percentage values in the 0..100 range."""
    return round(max(0.0, min(100.0, value)), 1)


def _parse_prometheus_text(text: str) -> MetricSeries:
    """Parse Prometheus text exposition into {metric_name: [(labels, value)]}."""
    result: MetricSeries = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            if "{" in line:
                name_part, rest = line.split("{", 1)
                labels_part, value_part = rest.rsplit("}", 1)
                labels = _parse_labels(labels_part)
                value = float(value_part.strip())
            else:
                name_part, value_part = line.split(None, 1)
                labels = {}
                value = float(value_part.strip())
            result.setdefault(name_part, []).append((labels, value))
        except (ValueError, IndexError):
            # Ignore exporter metadata or malformed lines without breaking a run.
            continue
    return result


def _parse_labels(label_str: str) -> dict[str, str]:
    """Parse a simple Prometheus label block into a dict."""
    labels: dict[str, str] = {}
    if not label_str:
        return labels

    # Small quoted-value parser; enough for snmp_exporter labels.
    i = 0
    while i < len(label_str):
        eq = label_str.find("=", i)
        if eq == -1:
            break
        key = label_str[i:eq].strip()
        q1 = label_str.find('"', eq)
        if q1 == -1:
            break

        q2 = q1 + 1
        escaped = False
        value_chars: list[str] = []
        while q2 < len(label_str):
            ch = label_str[q2]
            if escaped:
                value_chars.append(ch)
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                break
            else:
                value_chars.append(ch)
            q2 += 1

        labels[key] = "".join(value_chars)
        i = q2 + 1
        if i < len(label_str) and label_str[i] == ",":
            i += 1

    return labels


def _strict_number_from_text(value: str | None) -> float | None:
    """Convert clean numeric strings like '42' or '42 C' into floats."""
    if value is None:
        return None
    match = _STRICT_NUMBER.match(value)
    if not match:
        return None
    return float(match.group(1))


def _entry_number(metric_name: str, labels: dict[str, str], value: float) -> float:
    """Return a metric's numeric value, including DisplayString-as-label output.

    Some vendor MIB fields (notably WD PR4100) are DisplayString. Depending on
    snmp_exporter config, the real number may appear as a label while the sample
    value is only 1. In that case, use the label value.
    """
    if value not in (0.0, 1.0):
        return value

    preferred_label = labels.get(metric_name)
    parsed = _strict_number_from_text(preferred_label)
    if parsed is not None:
        return parsed

    metric_key = metric_name.lower()
    for key, label_value in labels.items():
        if key.lower().endswith(metric_key):
            parsed = _strict_number_from_text(label_value)
            if parsed is not None:
                return parsed

    return value


def _get_single(metrics: MetricSeries, names: tuple[str, ...] | list[str], default: float | None = None) -> float | None:
    """Get the first scalar value for one of several possible metric names."""
    for name in names:
        entries = metrics.get(name, [])
        if entries:
            labels, value = entries[0]
            return _entry_number(name, labels, value)
    return default


def _matching_value(
    metrics: MetricSeries,
    metric_name: str,
    reference_labels: dict[str, str],
    keys: tuple[str, ...],
) -> float | None:
    """Find a table metric row that shares one of the reference index labels."""
    for labels, value in metrics.get(metric_name, []):
        for key in keys:
            if key in reference_labels and labels.get(key) == reference_labels[key]:
                return _entry_number(metric_name, labels, value)
    return None


def _looks_like_real_storage(descr: str) -> bool:
    """Filter HOST-RESOURCES storage rows down to actual filesystems/volumes."""
    if not descr:
        return True

    lowered = descr.lower()
    excluded = ("memory", "swap", "virtual", "ram", "tmpfs", "devtmpfs")
    if any(token in lowered for token in excluded):
        return False

    # Prefer ordinary mount paths and Synology/WD volume descriptions.
    included = ("/", "volume", "share", "data", "storage")
    return any(token in lowered for token in included)


def _disk_used_from_hr_storage(metrics: MetricSeries) -> float | None:
    """Calculate disk usage from HOST-RESOURCES-MIB hrStorage* rows."""
    best_total = 0.0
    best_used_pct: float | None = None

    for labels, raw_size in metrics.get("hrStorageSize", []):
        descr = labels.get("hrStorageDescr", "")
        if not _looks_like_real_storage(descr):
            continue

        size = _entry_number("hrStorageSize", labels, raw_size)
        used = _matching_value(metrics, "hrStorageUsed", labels, ("hrStorageIndex", "hrStorageDescr"))
        alloc_units = _matching_value(
            metrics,
            "hrStorageAllocationUnits",
            labels,
            ("hrStorageIndex", "hrStorageDescr"),
        )
        if size <= 0 or used is None:
            continue

        total_bytes = size * (alloc_units or 1)
        used_pct = (used / size) * 100
        if total_bytes > best_total:
            best_total = total_bytes
            best_used_pct = used_pct

    return _clamp_pct(best_used_pct) if best_used_pct is not None else None


def _disk_used_from_synology_raid(metrics: MetricSeries) -> float | None:
    """Calculate disk usage from Synology RAID/volume total and free sizes."""
    best_total = 0.0
    best_used_pct: float | None = None
    best_is_volume = False

    for labels, raw_total in metrics.get("raidTotalSize", []):
        total = _entry_number("raidTotalSize", labels, raw_total)
        free = _matching_value(metrics, "raidFreeSize", labels, ("raidName", "raidIndex"))
        if total <= 0 or free is None:
            continue

        raid_name = labels.get("raidName", "")
        is_volume = "volume" in raid_name.lower()
        used_pct = ((total - free) / total) * 100

        if is_volume and not best_is_volume:
            best_total = total
            best_used_pct = used_pct
            best_is_volume = True
        elif is_volume == best_is_volume and total > best_total:
            best_total = total
            best_used_pct = used_pct

    return _clamp_pct(best_used_pct) if best_used_pct is not None else None


def _disk_used_from_wd_volume(metrics: MetricSeries) -> float | None:
    """Calculate disk usage from WD PR4100 volume size/free-space metrics."""
    best_total = 0.0
    best_used_pct: float | None = None

    for labels, raw_size in metrics.get("mycloudpr4100VolumeSize", []):
        size = _entry_number("mycloudpr4100VolumeSize", labels, raw_size)
        free = _matching_value(
            metrics,
            "mycloudpr4100VolumeFreeSpace",
            labels,
            ("mycloudpr4100VolumeNum", "mycloudpr4100VolumeName"),
        )
        if size <= 0 or free is None:
            continue

        used_pct = ((size - free) / size) * 100
        if size > best_total:
            best_total = size
            best_used_pct = used_pct

    return _clamp_pct(best_used_pct) if best_used_pct is not None else None


def _cpu_usage(metrics: MetricSeries) -> float:
    """Calculate CPU usage from UCD-SNMP ssCpu* percentages."""
    cpu_idle = _get_single(metrics, ("ssCpuIdle",))
    if cpu_idle is not None:
        return _clamp_pct(100 - cpu_idle)

    cpu_user = _get_single(metrics, ("ssCpuUser",), 0) or 0
    cpu_system = _get_single(metrics, ("ssCpuSystem",), 0) or 0
    return _clamp_pct(cpu_user + cpu_system)


def _ram_used_pct(metrics: MetricSeries) -> float:
    """Calculate RAM usage from UCD-SNMP memory counters in KiB."""
    mem_total = _get_single(metrics, ("memTotalReal",))
    if not mem_total or mem_total <= 0:
        return 0.0

    mem_avail = _get_single(metrics, ("memAvailReal",), 0) or 0
    mem_buffer = _get_single(metrics, ("memBuffer",), 0) or 0
    mem_cached = _get_single(metrics, ("memCached",), 0) or 0

    effective_free = min(mem_total, mem_avail + mem_buffer + mem_cached)
    used_pct = ((mem_total - effective_free) / mem_total) * 100
    return _clamp_pct(used_pct)


def _disk_used_pct(metrics: MetricSeries, profile: str) -> float:
    """Calculate disk usage using the best available MIB for the NAS profile."""
    hr_storage = _disk_used_from_hr_storage(metrics)
    if hr_storage is not None:
        return hr_storage

    if profile == "synology":
        raid = _disk_used_from_synology_raid(metrics)
        if raid is not None:
            return raid

    if profile == "wd":
        wd_volume = _disk_used_from_wd_volume(metrics)
        if wd_volume is not None:
            return wd_volume

    return 0.0


def _temperature(metrics: MetricSeries, names: tuple[str, ...]) -> float:
    """Read system temperature, falling back to the highest disk temperature."""
    temp = _get_single(metrics, names)
    if temp is not None:
        return round(temp, 1)

    disk_temps: list[float] = []
    for metric_name in ("diskTemperature", "mycloudpr4100DiskTemperature"):
        for labels, value in metrics.get(metric_name, []):
            disk_temps.append(_entry_number(metric_name, labels, value))

    return round(max(disk_temps), 1) if disk_temps else 0.0


def _system_uptime(metrics: MetricSeries) -> int:
    """Read sysUpTime and convert TimeTicks hundredths into seconds."""
    uptime_hundredths = _get_single(metrics, ("sysUpTime", "sysUpTimeInstance"), 0) or 0
    return int(uptime_hundredths / 100)


def _collect_normalized(metrics: MetricSeries, profile: str) -> list[dict]:
    """Normalize exporter output to the six NAS metrics used by the dashboard."""
    temp_names = {
        "synology": ("temperature", "synoSystemTemperature"),
        "wd": ("mycloudpr4100Temperature",),
    }.get(profile, ("temperature", "mycloudpr4100Temperature"))

    return [
        {"name": "cpu_usage", "value": _cpu_usage(metrics), "unit": "%"},
        {"name": "ram_used_pct", "value": _ram_used_pct(metrics), "unit": "%"},
        {"name": "disk_used_pct", "value": _disk_used_pct(metrics, profile), "unit": "%"},
        {"name": "temperature", "value": _temperature(metrics, temp_names), "unit": "C"},
        {"name": "system_uptime", "value": _system_uptime(metrics), "unit": "seconds"},
        {"name": "snmp_reachable", "value": 1, "unit": "bool"},
    ]


def _infer_profile(module: str | None, metrics: MetricSeries) -> str:
    """Infer NAS profile from config/module name, then metric names as fallback."""
    module_name = (module or "").lower()
    if any(token in module_name for token in ("synology", "syno")):
        return "synology"
    if any(token in module_name for token in ("wd", "mycloud", "pr4100")):
        return "wd"

    metric_names = set(metrics)
    if any(name.startswith("mycloudpr4100") for name in metric_names):
        return "wd"
    if {"raidTotalSize", "diskTemperature", "temperature"} & metric_names:
        return "synology"
    return "generic"


def _build_exporter_url(ip: str, exporter_url: str | None, module: str | None, exporter_port: int) -> str:
    """Build either centralized /snmp URL or legacy per-NAS /metrics URL."""
    if exporter_url:
        base = exporter_url.rstrip("&?")
        separator = "&" if "?" in base else "?"
        params = {"target": ip}
        if module:
            params["module"] = module
        return f"{base}{separator}{urlencode(params)}"
    return f"http://{ip}:{exporter_port}/metrics"


def get_snmp_nas_metrics(
    nas_id: str,
    ip: str,
    exporter_port: int = 9116,
    exporter_url: str | None = None,
    module: str | None = None,
    profile: str | None = None,
) -> list[dict]:
    """Scrape SNMP exporter and return API-compatible NAS metrics.

    If ``exporter_url`` is set, the collector uses centralized mode:
    ``<exporter_url>?target=<ip>&module=<module>``. Otherwise it keeps the
    legacy mode: ``http://<ip>:9116/metrics``.
    """
    url = _build_exporter_url(ip, exporter_url, module, exporter_port)
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to scrape SNMP exporter for %s at %s: %s", nas_id, url, exc)
        return _unreachable_metrics()

    metrics = _parse_prometheus_text(resp.text)
    resolved_profile = (profile or _infer_profile(module, metrics)).lower()
    logger.info("Collected SNMP metrics for %s via profile=%s module=%s", nas_id, resolved_profile, module or "-")
    return _collect_normalized(metrics, resolved_profile)
