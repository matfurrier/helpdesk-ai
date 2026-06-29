"""Add helpdesk.user_profiles for document fields (CPF, RG, matrícula, telefones).

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op

revision: str = "0011"
down_revision: str = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS helpdesk.user_profiles (
            user_uuid   varchar(36)  PRIMARY KEY,
            cpf         varchar(14),
            rg          varchar(20),
            matricula   varchar(30),
            phone       varchar(20),
            mobile      varchar(20),
            updated_at  timestamptz  NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS helpdesk.user_profiles")
