"""Compatibility command for adding the deterministic demo backup history."""

from app.database import SessionLocal
from app.seed import seed_backup_logs, seed_users


def seed_history() -> None:
    db = SessionLocal()
    try:
        users = seed_users(db)
        inserted = seed_backup_logs(db, users)
        print(f"Dummy backup history ready ({inserted} new rows).")
    finally:
        db.close()


if __name__ == "__main__":
    seed_history()
