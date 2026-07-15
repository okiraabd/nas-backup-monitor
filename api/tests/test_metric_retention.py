"""Metric retention worker tests."""
from datetime import datetime, timedelta, timezone

from app.models.metric import Metric
from app.services.metric_retention import delete_expired_metrics


def test_delete_expired_metrics_keeps_recent_rows(db_session):
    now = datetime.now(timezone.utc)
    expired = Metric(
        collected_at=now - timedelta(days=31),
        source_type="nas",
        source_id="retention-test",
        metric_name="cpu_usage",
        metric_value=1,
    )
    recent = Metric(
        collected_at=now - timedelta(days=1),
        source_type="nas",
        source_id="retention-test",
        metric_name="cpu_usage",
        metric_value=2,
    )
    db_session.add_all([expired, recent])
    db_session.commit()
    expired_id = expired.id
    recent_id = recent.id

    deleted = delete_expired_metrics(db_session, now - timedelta(days=30), batch_size=100)
    db_session.commit()

    assert deleted >= 1
    assert db_session.get(Metric, expired_id) is None
    assert db_session.get(Metric, recent_id) is not None
