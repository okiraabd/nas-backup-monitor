"""restore revoked token expiry index

Revision ID: 0004_revoked_token_expiry_idx
Revises: 0003_backup_log_idempotency
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0004_revoked_token_expiry_idx"
down_revision: Union[str, None] = "0003_backup_log_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Used by lazy cleanup in auth_service.revoke_token().
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_revoked_tokens_expires_at "
        "ON revoked_tokens (expires_at)"
    )


def downgrade() -> None:
    # Rollback removes only the restored helper index, not the revoked token data.
    op.execute("DROP INDEX IF EXISTS ix_revoked_tokens_expires_at")
