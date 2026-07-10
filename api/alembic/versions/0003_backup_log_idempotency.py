"""add backup log snapshot idempotency

Revision ID: 0003_backup_log_idempotency
Revises: 5a9cdcf4d9c1
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003_backup_log_idempotency"
down_revision: Union[str, None] = "5a9cdcf4d9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A successful Kopia snapshot may be reported more than once when the NAS
    # script retries. This constraint lets the API treat those retries as the
    # same backup event instead of creating duplicates.
    op.create_unique_constraint(
        "uq_backup_logs_nas_job_snapshot",
        "backup_logs",
        ["nas_id", "job_name", "snapshot_id"],
    )


def downgrade() -> None:
    # Remove the database-level guard if this migration is rolled back.
    op.drop_constraint(
        "uq_backup_logs_nas_job_snapshot",
        "backup_logs",
        type_="unique",
    )
