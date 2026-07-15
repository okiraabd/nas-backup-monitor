"""Batch deletion helpers for metric-history retention."""
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.metric import Metric


def delete_expired_metrics(db: Session, cutoff: datetime, batch_size: int) -> int:
    """Delete one oldest-first batch and return the number of removed rows."""
    expired_ids = db.scalars(
        select(Metric.id)
        .where(Metric.collected_at < cutoff)
        .order_by(Metric.collected_at.asc(), Metric.id.asc())
        .limit(batch_size)
    ).all()
    if not expired_ids:
        return 0

    db.execute(delete(Metric).where(Metric.id.in_(expired_ids)))
    return len(expired_ids)
