"""Add csat_token to user_satisfaction; make rating nullable before response.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0006"
down_revision: str = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Make rating nullable (NULL = not yet responded)
    conn.execute(
        text(
            "ALTER TABLE helpdesk.user_satisfaction "
            "ALTER COLUMN rating DROP NOT NULL"
        )
    )
    # Add csat_token column
    conn.execute(
        text(
            "ALTER TABLE helpdesk.user_satisfaction "
            "ADD COLUMN IF NOT EXISTS csat_token uuid UNIQUE DEFAULT gen_random_uuid()"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_user_satisfaction_csat_token "
            "ON helpdesk.user_satisfaction (csat_token)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DROP INDEX IF EXISTS helpdesk.ix_user_satisfaction_csat_token"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE helpdesk.user_satisfaction "
            "DROP COLUMN IF EXISTS csat_token"
        )
    )
    conn.execute(
        text(
            "ALTER TABLE helpdesk.user_satisfaction "
            "ALTER COLUMN rating SET NOT NULL"
        )
    )
