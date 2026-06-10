"""Make user_satisfaction.responded_at nullable (NULL = not yet responded).

Previously had NOT NULL DEFAULT now() which set responded_at immediately on INSERT,
making every CSAT invitation appear already-responded.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0007"
down_revision: str = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "ALTER TABLE helpdesk.user_satisfaction "
            "ALTER COLUMN responded_at DROP NOT NULL, "
            "ALTER COLUMN responded_at DROP DEFAULT"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "ALTER TABLE helpdesk.user_satisfaction "
            "ALTER COLUMN responded_at SET DEFAULT now(), "
            "ALTER COLUMN responded_at SET NOT NULL"
        )
    )
