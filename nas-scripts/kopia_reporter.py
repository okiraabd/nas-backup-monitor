#!/usr/bin/env python3
"""Kopia snapshot reporter helper.

This single helper is intentionally responsible for the parts that are awkward
or unsafe to do in shell:

- normalize Kopia's JSON into the Backup Monitor API payload shape;
- discover jobs from snapshot source metadata;
- reconcile unseen snapshot IDs per source;
- create synthetic failure events when Kopia cannot be queried;
- create pending payloads atomically;
- build/extract small auth JSON payloads for the shell delivery client.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReporterConfig:
    """Minimal runtime identity passed from the shell wrapper."""

    nas_id: str
    backup_engine: str = "kopia"


@dataclass(frozen=True)
class SourceInfo:
    key: str
    technical_source: str
    source_path: str
    job_name: str


def _parse_kopia_time(value: str | None) -> datetime | None:
    if not value:
        return None

    # Kopia can emit nanosecond precision. Python's datetime only stores
    # microseconds, so truncate safely before parsing.
    text = value.replace("Z", "+00:00")
    match = re.match(r"^(.*T\d{2}:\d{2}:\d{2})(\.\d+)?([+-]\d{2}:\d{2})$", text)
    if match:
        fraction = match.group(2) or ""
        if fraction:
            fraction = "." + fraction[1:7].ljust(6, "0")
        text = f"{match.group(1)}{fraction}{match.group(3)}"
    return datetime.fromisoformat(text)


def _safe_component(value: str) -> str:
    # Used for pending filenames, so keep it portable across NAS filesystems.
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    return cleaned[:128] or "unknown"


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "source"


def _basename(path: str) -> str:
    clean = path.rstrip("/")
    if not clean:
        return "root"
    return clean.rsplit("/", 1)[-1] or "root"


def _derive_source_info(snapshot: dict[str, Any], config: ReporterConfig) -> SourceInfo:
    """Derive a stable monitor job from Kopia's source/root metadata."""

    source = snapshot.get("source") or {}
    root_entry = snapshot.get("rootEntry") or {}

    source_path = source.get("path")
    if not isinstance(source_path, str) or not source_path:
        root_name = root_entry.get("name")
        source_path = f"/{root_name}" if isinstance(root_name, str) and root_name else "/unknown"

    root_name = root_entry.get("name")
    label = root_name if isinstance(root_name, str) and root_name else _basename(source_path)
    job_slug = _slugify(label)
    job_name = f"backup-{job_slug}"

    host = source.get("host")
    user_name = source.get("userName")
    technical_source = "{}@{}:{}".format(
        user_name if isinstance(user_name, str) and user_name else "unknown",
        host if isinstance(host, str) and host else "unknown",
        source_path,
    )

    # The state key intentionally uses the source path, not Kopia's host field.
    # In Docker-based Kopia deployments, source.host may be a container hostname
    # that can change after recreation, while the source path is the stable job
    # identity for our NAS use case.
    return SourceInfo(
        key=source_path,
        technical_source=technical_source,
        source_path=source_path,
        job_name=job_name,
    )


def normalize_snapshot(snapshot: dict[str, Any], config: ReporterConfig) -> dict[str, Any]:
    """Convert one Kopia snapshot-list item to the API LogIngest shape."""
    snapshot_id = snapshot.get("id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise ValueError("Kopia snapshot is missing a stable id")

    info = _derive_source_info(snapshot, config)
    stats = snapshot.get("stats") or {}
    summary = (snapshot.get("rootEntry") or {}).get("summ") or {}

    # API stores seconds; Kopia may report sub-second/nanosecond timestamps.
    start_text = snapshot.get("startTime")
    end_text = snapshot.get("endTime")
    started_at = _parse_kopia_time(start_text)
    ended_at = _parse_kopia_time(end_text)
    if started_at and ended_at:
        duration_seconds = math.ceil(max(0.0, (ended_at - started_at).total_seconds()))
    else:
        duration_seconds = None

    summary_file_count = summary.get("files")
    total_files = summary_file_count if isinstance(summary_file_count, int) and summary_file_count > 0 else None
    if total_files is None:
        stats_file_count = stats.get("fileCount")
        total_files = stats_file_count if isinstance(stats_file_count, int) and stats_file_count > 0 else None
    if total_files is None:
        # Some Kopia outputs report fileCount=0 but still expose cached/non-cached totals.
        total_files = (stats.get("cachedFiles") or 0) + (stats.get("nonCachedFiles") or 0)

    total_size = stats.get("totalSize")
    if total_size is None:
        total_size = summary.get("size")

    error_count = int(stats.get("errorCount") or 0)
    failed_entries = int(summary.get("numFailed") or 0)
    is_incomplete = bool(snapshot.get("incomplete") or snapshot.get("incompleteReason"))
    # Incomplete snapshots are useful to report, but should be visible as FAILED.
    is_failed = error_count > 0 or failed_entries > 0 or is_incomplete or ended_at is None

    return {
        "nas_id": config.nas_id,
        "job_name": info.job_name,
        "source_path": info.source_path,
        "source_ip": None,
        "destination_target": None,
        "backup_engine": config.backup_engine,
        "status": "FAILED" if is_failed else "SUCCESS",
        "snapshot_id": snapshot_id,
        "started_at": start_text,
        "ended_at": end_text,
        "duration_seconds": duration_seconds,
        "total_size_bytes": total_size,
        "total_files": total_files,
        "changed_file_count": stats.get("nonCachedFiles"),
        "cached_files": stats.get("cachedFiles"),
        "non_cached_files": stats.get("nonCachedFiles"),
        "dir_count": stats.get("dirCount") if stats.get("dirCount") is not None else summary.get("dirs"),
        "error_count": error_count,
        "ignored_error_count": int(stats.get("ignoredErrorCount") or 0),
        "retention_reason": snapshot.get("retentionReason") or [],
        "message": (
            "Kopia snapshot completed successfully"
            if not is_failed
            else "Kopia snapshot completed with errors or is incomplete"
        ),
        "raw_payload": snapshot,
    }


def _load_state(path: Path) -> dict[str, Any]:
    """Load local reconciliation cache; PostgreSQL remains the final source of truth."""

    if not path.exists():
        return {"version": 2, "sources": {}}
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict):
        raise ValueError(f"Invalid reporter state: {path}")
    sources = state.get("sources")
    if not isinstance(sources, dict):
        raise ValueError(f"Invalid reporter state sources: {path}")
    return state


def _atomic_replace_json(path: Path, value: Any) -> None:
    """Write state atomically so an interrupted run does not corrupt JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _create_pending_once(path: Path, payload: dict[str, Any]) -> bool:
    """Create one pending payload without overwriting an existing retry file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise
    return True


def _snapshot_sort_key(snapshot: dict[str, Any]) -> tuple[str, str]:
    return (snapshot.get("endTime") or snapshot.get("startTime") or "", snapshot.get("id") or "")


def reconcile_snapshots(
    snapshots: list[dict[str, Any]],
    *,
    config: ReporterConfig,
    state_path: Path,
    pending_dir: Path,
) -> dict[str, int]:
    """Queue unseen snapshots per discovered Kopia source."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    source_info_by_key: dict[str, SourceInfo] = {}
    # Reconcile per source path so multiple Kopia jobs on one NAS stay independent.
    for snapshot in snapshots:
        if not isinstance(snapshot.get("id"), str) or not snapshot["id"]:
            raise ValueError("Every Kopia snapshot must include an id")
        info = _derive_source_info(snapshot, config)
        grouped.setdefault(info.key, []).append(snapshot)
        source_info_by_key[info.key] = info

    state = _load_state(state_path)
    state_sources = state.setdefault("sources", {})
    if not isinstance(state_sources, dict):
        raise ValueError(f"Invalid reporter state sources: {state_path}")

    scanned = 0
    unseen = 0
    created = 0
    already_pending = 0

    for source_key, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=_snapshot_sort_key)
        scanned += len(ordered)

        source_state = state_sources.get(source_key)
        source_state_exists = isinstance(source_state, dict)
        if not source_state_exists:
            source_state = {"seen_snapshot_ids": []}

        ids = source_state.get("seen_snapshot_ids", [])
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            raise ValueError(f"Invalid seen_snapshot_ids for source {source_key}")
        seen_ids = set(ids)
        visible_ids = [row["id"] for row in ordered]

        if not source_state_exists:
            # First run: send only the latest visible snapshot, baseline the older ones.
            candidates = ordered[-1:] if ordered else []
            intentionally_seen = set(visible_ids[:-1])
        else:
            candidates = [row for row in ordered if row["id"] not in seen_ids]
            intentionally_seen = set()

        source_info = source_info_by_key[source_key]
        queued_ids: set[str] = set()
        for snapshot in candidates:
            # Pending filename includes snapshot ID, making retries naturally idempotent.
            payload = normalize_snapshot(snapshot, config)
            pending_name = "__".join(
                _safe_component(part)
                for part in (config.nas_id, payload["job_name"], snapshot["id"])
            )
            pending_path = pending_dir / f"{pending_name}.json"
            if _create_pending_once(pending_path, payload):
                created += 1
            else:
                already_pending += 1
            queued_ids.add(snapshot["id"])

        unseen += len(candidates)
        seen_ids.update(intentionally_seen)
        seen_ids.update(queued_ids)
        state_sources[source_key] = {
            "job_name": source_info.job_name,
            "source_path": source_info.source_path,
            "technical_source": source_info.technical_source,
            "seen_snapshot_ids": sorted(seen_ids),
        }

    state["version"] = 2
    state["nas_id"] = config.nas_id
    state["last_scan_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_replace_json(state_path, state)

    return {
        "scanned": scanned,
        "sources": len(grouped),
        "unseen": unseen,
        "created": created,
        "already_pending": already_pending,
    }


def _known_sources_from_state(state_path: Path) -> list[dict[str, str | None]]:
    """Return previously discovered sources, or one generic repository source."""
    try:
        state = _load_state(state_path)
        sources = state.get("sources", {})
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        sources = {}

    known_sources: list[dict[str, str | None]] = []
    if isinstance(sources, dict):
        for source_key, source in sorted(sources.items()):
            if not isinstance(source, dict):
                continue
            job_name = source.get("job_name")
            source_path = source.get("source_path")
            known_sources.append(
                {
                    "source_key": source_key if isinstance(source_key, str) else None,
                    "job_name": job_name if isinstance(job_name, str) and job_name else "kopia-repository",
                    "source_path": source_path if isinstance(source_path, str) and source_path else None,
                }
            )

    if known_sources:
        return known_sources

    return [
        {
            "source_key": None,
            "job_name": "kopia-repository",
            "source_path": None,
        }
    ]


def _queue_failure_event(
    *,
    diagnostic: str,
    config: ReporterConfig,
    state_path: Path,
    pending_dir: Path,
    event_type: str,
    message: str,
    filename_prefix: str,
) -> dict[str, int]:
    """Queue FAILED log events for failures that happen before a snapshot exists."""
    occurred_at = datetime.now(timezone.utc)
    event_id = occurred_at.isoformat(timespec="microseconds")
    diagnostic = diagnostic.strip()
    if len(diagnostic) > 4000:
        diagnostic = diagnostic[-4000:]

    created = 0
    already_pending = 0
    sources = _known_sources_from_state(state_path)

    for source in sources:
        job_name = source["job_name"] or "kopia-repository"
        payload = {
            "nas_id": config.nas_id,
            "job_name": job_name,
            "source_path": source["source_path"],
            "source_ip": None,
            "destination_target": None,
            "backup_engine": config.backup_engine,
            "status": "FAILED",
            "snapshot_id": None,
            "started_at": occurred_at.isoformat(),
            "ended_at": occurred_at.isoformat(),
            "duration_seconds": 0,
            "total_size_bytes": None,
            "total_files": None,
            "changed_file_count": None,
            "cached_files": None,
            "non_cached_files": None,
            "dir_count": None,
            "error_count": 1,
            "ignored_error_count": 0,
            "retention_reason": [],
            "message": message,
            "raw_payload": {
                "event_type": event_type,
                "generated_at": occurred_at.isoformat(),
                "state_source_key": source["source_key"],
                "diagnostic": diagnostic,
            },
        }
        source_component = source["source_key"] or source["source_path"] or "repository"
        pending_name = "__".join(
            _safe_component(part)
            for part in (config.nas_id, job_name, source_component, f"{filename_prefix}-{event_id}")
        )
        pending_path = pending_dir / f"{pending_name}.json"
        if _create_pending_once(pending_path, payload):
            created += 1
        else:
            already_pending += 1

    return {
        "sources": len(sources),
        "created": created,
        "already_pending": already_pending,
    }


def queue_repository_error(
    *,
    diagnostic: str,
    config: ReporterConfig,
    state_path: Path,
    pending_dir: Path,
) -> dict[str, int]:
    """Queue FAILED log events for repository-level Kopia errors."""
    return _queue_failure_event(
        diagnostic=diagnostic,
        config=config,
        state_path=state_path,
        pending_dir=pending_dir,
        event_type="kopia_snapshot_query_failed",
        message="Kopia repository could not be queried; backup result was reported before snapshot creation.",
        filename_prefix="repository-error",
    )


def queue_container_not_running(
    *,
    diagnostic: str,
    config: ReporterConfig,
    state_path: Path,
    pending_dir: Path,
) -> dict[str, int]:
    """Queue FAILED log events when the Kopia container is stopped."""
    return _queue_failure_event(
        diagnostic=diagnostic,
        config=config,
        state_path=state_path,
        pending_dir=pending_dir,
        event_type="kopia_container_not_running",
        message="Kopia container is not running; backup result was reported before snapshot scan.",
        filename_prefix="container-not-running",
    )


def build_login_payload(raw: bytes) -> dict[str, str]:
    """Build auth JSON from NUL-delimited username/password supplied by shell."""

    parts = raw.split(b"\0", 1)
    if len(parts) != 2:
        raise ValueError("expected NUL-delimited username and password")
    return {
        "username": parts[0].decode("utf-8"),
        "password": parts[1].decode("utf-8"),
    }


def extract_access_token(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ValueError("login response must be a JSON object")
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("login response did not contain an access token")
    return token


def _add_reconcile_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--pending-dir", required=True, type=Path)
    parser.add_argument("--nas-id", required=True)


def _add_queue_error_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--pending-dir", required=True, type=Path)
    parser.add_argument("--nas-id", required=True)


def _build_parser() -> argparse.ArgumentParser:
    """Expose tiny subcommands used by the shell wrapper."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    reconcile_parser = subparsers.add_parser("reconcile", help="normalize snapshots and create pending logs")
    _add_reconcile_args(reconcile_parser)

    queue_error_parser = subparsers.add_parser(
        "queue-repository-error",
        help="create FAILED pending logs when Kopia cannot query the repository",
    )
    _add_queue_error_args(queue_error_parser)

    queue_container_parser = subparsers.add_parser(
        "queue-container-not-running",
        help="create FAILED pending logs when the Kopia container is stopped",
    )
    _add_queue_error_args(queue_container_parser)

    subparsers.add_parser("login-payload", help="read username/password from stdin and emit JSON")
    subparsers.add_parser("extract-token", help="read login response JSON and print access token")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.command == "login-payload":
            print(json.dumps(build_login_payload(sys.stdin.buffer.read()), ensure_ascii=False, separators=(",", ":")))
            return 0
        if args.command == "extract-token":
            print(extract_access_token(json.load(sys.stdin)))
            return 0
        if args.command == "queue-repository-error":
            result = queue_repository_error(
                diagnostic=sys.stdin.read(),
                config=ReporterConfig(
                    nas_id=args.nas_id,
                ),
                state_path=args.state,
                pending_dir=args.pending_dir,
            )
            print(json.dumps(result, separators=(",", ":")))
            return 0
        if args.command == "queue-container-not-running":
            result = queue_container_not_running(
                diagnostic=sys.stdin.read(),
                config=ReporterConfig(
                    nas_id=args.nas_id,
                ),
                state_path=args.state,
                pending_dir=args.pending_dir,
            )
            print(json.dumps(result, separators=(",", ":")))
            return 0

        with args.input.open("r", encoding="utf-8") as handle:
            snapshots = json.load(handle)
        if not isinstance(snapshots, list):
            raise ValueError("Kopia snapshot output must be a JSON array")

        result = reconcile_snapshots(
            snapshots,
            config=ReporterConfig(
                nas_id=args.nas_id,
            ),
            state_path=args.state,
            pending_dir=args.pending_dir,
        )
        print(json.dumps(result, separators=(",", ":")))
        return 0
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Kopia reporter helper failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
