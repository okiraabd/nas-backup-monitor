"""Seed initial users and, optionally, a small demo dataset.

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


def seed_backup_logs(db: Session, users: dict[str, User]) -> None:
    """Create a handful of backup logs (mix of SUCCESS and FAILED)."""
    if db.scalar(select(BackupLog).limit(1)) is not None:
        return  # already seeded

    syn = users["nas-synology"].id
    wd = users["nas-wd"].id
    now = _now()

    logs = [
        BackupLog(
            nas_id="synology-ds1522", job_name="backup-makuku", source_path="/MAKUKU",
            source_ip="192.168.1.10", destination_target="Ceph S3", backup_engine="kopia",
            status="SUCCESS", snapshot_id="05845bf9e1c2aeaf097fb906fd1eda28",
            started_at=now - timedelta(hours=6), ended_at=now - timedelta(hours=6, seconds=-95),
            duration_seconds=95, total_size_bytes=154241124981, total_files=11579,
            changed_file_count=12, cached_files=11500, non_cached_files=79, dir_count=43,
            error_count=0, ignored_error_count=0, retention_reason=["latest-5"],
            message="Kopia snapshot completed successfully", raw_payload={"demo": True},
            reported_by=syn,
        ),
        BackupLog(
            nas_id="wd-pr4100", job_name="backup-finance", source_path="/FINANCE",
            source_ip="192.168.1.11", destination_target="Ceph S3", backup_engine="kopia",
            status="SUCCESS", snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            started_at=now - timedelta(hours=5), ended_at=now - timedelta(hours=5, seconds=-140),
            duration_seconds=140, total_size_bytes=88123456789, total_files=6540,
            changed_file_count=30, cached_files=6480, non_cached_files=60, dir_count=88,
            error_count=0, ignored_error_count=0, retention_reason=["latest-5", "weekly-4"],
            message="Kopia snapshot completed successfully", raw_payload={"demo": True},
            reported_by=wd,
        ),
        BackupLog(
            nas_id="synology-ds1522", job_name="backup-hrd", source_path="/HRD",
            source_ip="192.168.1.10", destination_target="Ceph S3", backup_engine="kopia",
            status="FAILED", snapshot_id=None,
            started_at=now - timedelta(hours=4), ended_at=now - timedelta(hours=4, seconds=-20),
            duration_seconds=20, total_size_bytes=None, total_files=None,
            error_count=3, ignored_error_count=0, retention_reason=None,
            message="Failed to upload snapshot: S3 connection reset", raw_payload={"demo": True},
            reported_by=syn, acknowledged=False,
        ),
        BackupLog(
            nas_id="wd-pr4100", job_name="backup-design", source_path="/DESIGN",
            source_ip="192.168.1.11", destination_target="Ceph S3", backup_engine="kopia",
            status="SUCCESS", snapshot_id="f0e1d2c3b4a5968778695a4b3c2d1e0f",
            started_at=now - timedelta(hours=3), ended_at=now - timedelta(hours=3, seconds=-210),
            duration_seconds=210, total_size_bytes=203400000000, total_files=20345,
            changed_file_count=105, cached_files=20200, non_cached_files=145, dir_count=310,
            error_count=0, ignored_error_count=1, retention_reason=["latest-5"],
            message="Kopia snapshot completed successfully", raw_payload={"demo": True},
            reported_by=wd,
        ),
        BackupLog(
            nas_id="synology-ds1522", job_name="backup-makuku", source_path="/MAKUKU",
            source_ip="192.168.1.10", destination_target="Ceph S3", backup_engine="kopia",
            status="FAILED", snapshot_id=None,
            started_at=now - timedelta(hours=2), ended_at=now - timedelta(hours=2, seconds=-15),
            duration_seconds=15, error_count=1, ignored_error_count=0,
            message="Kopia repository locked by another process", raw_payload={"demo": True},
            reported_by=syn, acknowledged=True, acknowledged_by=users["admin"].id,
            acknowledged_at=now - timedelta(hours=1),
            remark="Sudah dicek, proses backup lain masih berjalan. Aman.",
        ),
    ]
    db.add_all(logs)
    db.commit()


def seed_metrics(db: Session, users: dict[str, User]) -> None:
    """Create recent metrics for two NAS devices and the Ceph cluster."""
    if db.scalar(select(Metric).limit(1)) is not None:
        return

    collector_id = users["collector"].id
    now = _now()

    def nas_metrics(source_id: str, cpu: float, ram: float, disk: float, temp: float, at: datetime):
        return [
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="cpu_usage", metric_value=cpu, unit="%", collected_by=collector_id),
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="ram_used_pct", metric_value=ram, unit="%", collected_by=collector_id),
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="disk_used_pct", metric_value=disk, unit="%", collected_by=collector_id),
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="temperature", metric_value=temp, unit="C", collected_by=collector_id),
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="system_uptime", metric_value=1209600, unit="seconds", collected_by=collector_id),
            Metric(collected_at=at, source_type="nas", source_id=source_id,
                   metric_name="snmp_reachable", metric_value=1, unit="bool", collected_by=collector_id),
        ]

    def ceph_metrics(at: datetime, used_pct: float, read_iops: float, write_iops: float):
        return [
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="health_status", metric_text="HEALTH_OK", unit="status", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="osd_up", metric_value=3, unit="count", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="osd_total", metric_value=3, unit="count", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="storage_used_pct", metric_value=used_pct, unit="%", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="storage_used_bytes", metric_value=1200000000000, unit="bytes", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="storage_total_bytes", metric_value=3000000000000, unit="bytes", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="read_iops", metric_value=read_iops, unit="iops", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="write_iops", metric_value=write_iops, unit="iops", collected_by=collector_id),
            Metric(collected_at=at, source_type="ceph", source_id="ceph-cluster",
                   metric_name="ceph_reachable", metric_value=1, unit="bool", collected_by=collector_id),
        ]

    all_metrics: list[Metric] = []
    # A few history points (every ~2 min going back), latest is "now" => fresh.
    for i in range(5):
        at = now - timedelta(minutes=2 * i)
        all_metrics += nas_metrics("synology-ds1522", 23 + i, 61 - i, 57, 42 + i * 0.5, at)
        all_metrics += nas_metrics("wd-pr4100", 15 + i, 48 + i, 63, 39 + i * 0.4, at)
        all_metrics += ceph_metrics(at, 45.2 + i * 0.3, 12 + i, 8 + i)

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
        seed_backup_logs(db, users)
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
