"""Periodic metric retention worker, intended to run as a separate process."""
import logging
import time
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import SessionLocal
from app.services.metric_retention import delete_expired_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def cleanup_once() -> int:
    """Delete all expired metrics in bounded transactions."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.metric_retention_days)
    total_deleted = 0

    with SessionLocal() as db:
        while True:
            deleted = delete_expired_metrics(db, cutoff, settings.metric_cleanup_batch_size)
            db.commit()
            total_deleted += deleted
            if deleted < settings.metric_cleanup_batch_size:
                break

    return total_deleted


def main() -> None:
    logger.info(
        "Metric cleanup started: retention=%sd interval=%ss batch=%s",
        settings.metric_retention_days,
        settings.metric_cleanup_interval_seconds,
        settings.metric_cleanup_batch_size,
    )
    while True:
        try:
            deleted = cleanup_once()
            logger.info("Metric cleanup complete: deleted=%s", deleted)
        except Exception:
            logger.exception("Metric cleanup failed; retrying on the next interval")
        time.sleep(settings.metric_cleanup_interval_seconds)


if __name__ == "__main__":
    main()
