"""Create helpdesk.role_overrides; add idempotency guard for convert; July audit partition.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-09
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0003"
down_revision: str = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- role_overrides --------------------------------------------------
    # Stores explicit helpdesk-role grants for users who need it_admin or
    # it_lead access. Consulted by role_resolver.py before departmentid.
    # NOT NULL on granted_at: privilege grants must always be timestamped.
    conn.execute(
        text("""
            CREATE TABLE IF NOT EXISTS helpdesk.role_overrides (
              user_uuid   text PRIMARY KEY,
              role        text NOT NULL
                CHECK (role IN ('it_admin', 'it_lead')),
              granted_by  text NOT NULL,
              granted_at  timestamptz NOT NULL DEFAULT now()
            )
        """)
    )

    # --- Idempotency guard: one ticket per conversation -------------------
    # Prevents duplicate tickets if POST /convert is called twice (F-01).
    # A partial unique index is cheaper than a trigger and enforced at the
    # DB layer so no application-level lock is needed.
    conn.execute(
        text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_conv_one_ticket
              ON helpdesk.ai_conversations (id)
              WHERE status = 'converted'
        """)
    )

    # --- audit_log July 2026 partition ------------------------------------
    conn.execute(
        text("""
            CREATE TABLE IF NOT EXISTS helpdesk.audit_log_y2026m07
              PARTITION OF helpdesk.audit_log
              FOR VALUES FROM ('2026-07-01') TO ('2026-08-01')
        """)
    )

    # --- Validate FK that was created NOT VALID in 0001 ------------------
    # SHARE UPDATE EXCLUSIVE lock — does not block reads or DML.
    conn.execute(
        text("""
            ALTER TABLE helpdesk.ai_conversations
              VALIDATE CONSTRAINT fk_ai_conv_ticket
        """)
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text("ALTER TABLE helpdesk.ai_conversations DROP CONSTRAINT IF EXISTS fk_ai_conv_ticket")
    )
    conn.execute(text("DROP TABLE IF EXISTS helpdesk.audit_log_y2026m07"))
    conn.execute(text("DROP INDEX IF EXISTS helpdesk.uq_conv_one_ticket"))
    conn.execute(text("DROP TABLE IF EXISTS helpdesk.role_overrides"))
