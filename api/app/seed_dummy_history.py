from datetime import datetime, timezone, timedelta
from app.database import SessionLocal
from app.models.backup_log import BackupLog
import random

def seed_history():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        
        # Add 6 days of historical data
        for i in range(1, 7):
            day = now - timedelta(days=i)
            
            # Generate random number of success logs (5-15)
            num_success = random.randint(5, 15)
            for j in range(num_success):
                db.add(BackupLog(
                    nas_id="synology-ds1522" if j % 2 == 0 else "wd-pr4100",
                    job_name=f"backup-history-{i}-{j}",
                    source_path="/DUMMY",
                    source_ip="192.168.1.10",
                    destination_target="Ceph S3",
                    backup_engine="kopia",
                    status="SUCCESS",
                    started_at=day - timedelta(hours=random.randint(1, 10)),
                    ended_at=day - timedelta(hours=random.randint(1, 10), minutes=-10),
                    duration_seconds=600,
                    reported_by=3, # service ID usually
                    created_at=day
                ))
            
            # Generate random number of failed logs (0-3)
            num_failed = random.randint(0, 3)
            for j in range(num_failed):
                db.add(BackupLog(
                    nas_id="synology-ds1522",
                    job_name=f"backup-failed-{i}-{j}",
                    source_path="/DUMMY",
                    source_ip="192.168.1.10",
                    destination_target="Ceph S3",
                    backup_engine="kopia",
                    status="FAILED",
                    started_at=day - timedelta(hours=random.randint(1, 10)),
                    ended_at=day - timedelta(hours=random.randint(1, 10), minutes=-10),
                    duration_seconds=600,
                    error_count=1,
                    message="Dummy history failure",
                    reported_by=3,
                    acknowledged=False,
                    created_at=day
                ))
        
        # Also add a fresh failed log for today (unacknowledged) to ensure the ack feature can be tested
        db.add(BackupLog(
            nas_id="wd-pr4100",
            job_name="backup-critical",
            source_path="/DATA",
            source_ip="192.168.1.11",
            destination_target="Ceph S3",
            backup_engine="kopia",
            status="FAILED",
            started_at=now - timedelta(hours=1),
            ended_at=now - timedelta(hours=1, minutes=-5),
            duration_seconds=300,
            error_count=5,
            message="Connection timeout during snapshot",
            reported_by=3,
            acknowledged=False,
            created_at=now
        ))

        db.commit()
        print("Dummy history seeded successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_history()
