"""Seed initial users and, optionally, a representative demo dataset.

Idempotent: running twice will not duplicate users or demo rows. Run with:
    python -m app.seed users  # accounts only
    python -m app.seed demo   # accounts + demo logs/metrics
"""
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.backup_log import BackupLog
from app.models.collector_run import CollectorRun
from app.models.metric import Metric
from app.models.user import User
from app.security import hash_password

# username / password / display_name / role
SEED_USERS = [
    ("admin", "admin123", "Administrator", "admin"),
    ("nas-synology", "synology123", "NAS Synology DS1522+", "service"),
    ("nas-wd", "wd123", "NAS WD PR4100", "service"),
    ("collector", "collector123", "Metric Collector", "collector"),
    ("operator", "operator", "NOC Operator", "operator"),
]

SEED_MODES = {"users", "demo"}
DEMO_BACKUP_DAYS = 30

# source_id, job_name, source_path, source_ip, service username, base bytes, base files
DEMO_BACKUP_JOBS = (
    (
        "synology-ds1522", "backup-makuku", "/MAKUKU", "192.168.24.5",
        "nas-synology", 154_241_124_981, 11_579,
    ),
    (
        "synology-ds1522", "backup-hrd", "/HRD", "192.168.24.5",
        "nas-synology", 52_480_000_000, 4_920,
    ),
    (
        "wd-pr4100", "backup-finance", "/FINANCE", "192.168.24.4",
        "nas-wd", 88_123_456_789, 6_540,
    ),
    (
        "wd-pr4100", "backup-design", "/DESIGN", "192.168.24.4",
        "nas-wd", 203_400_000_000, 20_345,
    ),
)

DEMO_FAILURE_MESSAGES = (
    "S3 endpoint timed out while uploading pack files",
    "Kopia repository is locked by another maintenance task",
    "Source path became unavailable during the snapshot",
    "Insufficient temporary space for the snapshot cache",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def seed_users(db: Session) -> dict[str, User]:
    """Create seed users if absent. Returns username -> User map."""
    users: dict[str, User] = {}
    for username, password, display_name, role in SEED_USERS:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                role=role,
                is_active=True,
            )
            db.add(user)
            db.flush()
        users[username] = user
    db.commit()
    return users


def seed_backup_logs(db: Session, users: dict[str, User]) -> int:
    """Create 30 days of deterministic, idempotent backup history."""
    now = _now()
    logs: list[BackupLog] = []

    for day_offset in range(DEMO_BACKUP_DAYS):
        for job_index, (
            nas_id,
            job_name,
            source_path,
            source_ip,
            service_username,
            base_size,
            base_files,
        ) in enumerate(DEMO_BACKUP_JOBS):
            snapshot_id = f"demo-v2-{day_offset:02d}-{job_name}"
            duration_seconds = 75 + ((day_offset * 31 + job_index * 47) % 420)
            started_at = now - timedelta(
                days=day_offset,
                hours=job_index * 2 + 1,
                minutes=(day_offset * 7 + job_index * 3) % 40,
            )
            ended_at = started_at + timedelta(seconds=duration_seconds)
            failed = (day_offset + job_index * 2) % 9 == 0
            acknowledged = failed and (day_offset + job_index) % 2 == 1
            changed_files = 8 + ((day_offset * 17 + job_index * 29) % 180)
            total_files = base_files + day_offset * 4 + job_index * 11
            total_size = base_size + day_offset * 75_000_000 + job_index * 12_500_000

            logs.append(
                BackupLog(
                    nas_id=nas_id,
                    job_name=job_name,
                    source_path=source_path,
                    source_ip=source_ip,
                    destination_target="Ceph S3",
                    backup_engine="kopia",
                    status="FAILED" if failed else "SUCCESS",
                    snapshot_id=snapshot_id,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_seconds=duration_seconds,
                    total_size_bytes=None if failed else total_size,
                    total_files=None if failed else total_files,
                    changed_file_count=None if failed else changed_files,
                    cached_files=None if failed else total_files - changed_files,
                    non_cached_files=None if failed else changed_files,
                    dir_count=None if failed else max(12, total_files // 65),
                    error_count=1 + (day_offset % 3) if failed else 0,
                    ignored_error_count=0 if failed else (day_offset + job_index) % 2,
                    retention_reason=(
                        None
                        if failed
                        else (["latest-5", "weekly-4"] if day_offset % 7 == 0 else ["latest-5"])
                    ),
                    message=(
                        DEMO_FAILURE_MESSAGES[(day_offset + job_index) % len(DEMO_FAILURE_MESSAGES)]
                        if failed
                        else "Kopia snapshot completed successfully"
                    ),
                    raw_payload={
                        "demo": True,
                        "seed_version": 2,
                        "day_offset": day_offset,
                        "job_index": job_index,
                    },
                    reported_by=users[service_username].id,
                    acknowledged=acknowledged,
                    acknowledged_by=users["admin"].id if acknowledged else None,
                    acknowledged_at=ended_at + timedelta(minutes=30) if acknowledged else None,
                    remark=(
                        "Reviewed by the demo administrator; a retry completed successfully."
                        if acknowledged
                        else None
                    ),
                    created_at=ended_at,
                )
            )

    snapshot_ids = [log.snapshot_id for log in logs if log.snapshot_id is not None]
    existing_ids = set(
        db.scalars(
            select(BackupLog.snapshot_id).where(BackupLog.snapshot_id.in_(snapshot_ids))
        ).all()
    )
    new_logs = [log for log in logs if log.snapshot_id not in existing_ids]
    db.add_all(new_logs)
    db.commit()
    return len(new_logs)


def seed_metrics(db: Session, users: dict[str, User]) -> None:
    """Create recent metrics for two NAS devices and the Ceph cluster."""
    if db.scalar(select(Metric).limit(1)) is not None:
        return

    collector_id = users["collector"].id
    now = _now()

    def nas_metrics(source_id: str, cpu: float, ram: float, disk: float, at: datetime):
        return [
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="cpu_usage", metric_value=cpu, unit="%", collected_by=collector_id),
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="ram_used_pct", metric_value=ram, unit="%", collected_by=collector_id),
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="disk_used_pct", metric_value=disk, unit="%", collected_by=collector_id),
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="system_uptime", metric_value=1209600, unit="seconds", collected_by=collector_id),
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="snmp_reachable", metric_value=1, unit="bool", collected_by=collector_id),
        ]

    def ceph_metrics(at: datetime, used_pct: float):
        return [
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="health_status", metric_text="HEALTH_OK", unit="status", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="osd_up", metric_value=3, unit="count", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="osd_in", metric_value=3, unit="count", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="osd_total", metric_value=3, unit="count", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="storage_used_pct", metric_value=used_pct, unit="%", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="storage_used_bytes", metric_value=1200000000000, unit="bytes", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="storage_total_bytes", metric_value=3000000000000, unit="bytes", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="ceph_reachable", metric_value=1, unit="bool", collected_by=collector_id),
        ]

    all_metrics: list[Metric] = []
    # A few history points (every ~2 min going back), latest is "now" => fresh.
    for i in range(5):
        at = now - timedelta(minutes=2 * i)
        all_metrics += nas_metrics("synology-ds1522", 23 + i, 61 - i, 57, at)
        all_metrics += nas_metrics("wd-pr4100", 15 + i, 48 + i, 63, at)
        all_metrics += ceph_metrics(at, 45.2 + i * 0.3)

    db.add_all(all_metrics)
    db.commit()


def seed_collector_run(db: Session) -> None:
    """Create one recent collector run record."""
    if db.scalar(select(CollectorRun).limit(1)) is not None:
        return
    now = _now()
    db.add(
        CollectorRun(
            started_at=now - timedelta(seconds=5), finished_at=now, status="SUCCESS",
            is_mock=True, message="Demo metrics generated successfully",
            total_sources=3, success_sources=3, failed_sources=0,
        )
    )
    db.commit()


def run(mode: str = "demo") -> None:
    """Run the requested seed mode."""
    mode = mode.strip().lower()
    if mode not in SEED_MODES:
        raise SystemExit(f"Invalid seed mode '{mode}'. Use: users or demo.")

    db = SessionLocal()
    try:
        print("Seeding users...")
        users = seed_users(db)

        if mode == "users":
            print("Seed users complete.")
            return

        print("Seeding backup logs...")
        inserted_logs = seed_backup_logs(db, users)
        print(f"Backup logs ready ({inserted_logs} new demo rows).")
        print("Seeding metrics...")
        seed_metrics(db, users)
        print("Seeding collector run...")
        seed_collector_run(db)
        print("Seed complete.")
    finally:
        db.close()


def main() -> None:
    """CLI entrypoint. Defaults to demo for backward compatibility."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    run(mode)


if __name__ == "__main__":
    main()
