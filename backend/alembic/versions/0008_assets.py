"""Add asset management tables (helpdesk.assets + helpdesk.asset_history).

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-15
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0008"
down_revision: str = "0007"
branch_labels = None
depends_on = None

_SQL_UP = """
CREATE TABLE helpdesk.assets (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_tag      text UNIQUE,
    asset_type     text NOT NULL
                   CHECK (asset_type IN ('notebook','smartphone','tablet','other')),
    brand          text,
    model          text NOT NULL,
    serial_number  text,
    status         text NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active','maintenance','retired','lost')),
    holder_id      text,
    holder_name    text,
    holder_dept    text,
    acquired_at    date,
    warranty_until date,
    specs          jsonb NOT NULL DEFAULT '{}',
    compliance     jsonb NOT NULL DEFAULT '{}',
    notes          text,
    created_by     text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE helpdesk.asset_history (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id    uuid NOT NULL REFERENCES helpdesk.assets(id) ON DELETE CASCADE,
    action      text NOT NULL
                CHECK (action IN ('created','assigned','returned','status_changed','updated')),
    holder_name text,
    holder_dept text,
    changed_by  text NOT NULL,
    changed_at  timestamptz NOT NULL DEFAULT now(),
    before_data jsonb,
    after_data  jsonb,
    notes       text
);

CREATE INDEX ix_assets_type   ON helpdesk.assets (asset_type);
CREATE INDEX ix_assets_status ON helpdesk.assets (status);
CREATE INDEX ix_assets_holder ON helpdesk.assets (holder_id);
CREATE INDEX ix_asset_hist_asset ON helpdesk.asset_history (asset_id, changed_at DESC);

CREATE TRIGGER tg_assets_updated
    BEFORE UPDATE ON helpdesk.assets
    FOR EACH ROW EXECUTE FUNCTION helpdesk.tg_set_updated_at();
"""

_SQL_DOWN = """
DROP TABLE IF EXISTS helpdesk.asset_history CASCADE;
DROP TABLE IF EXISTS helpdesk.assets CASCADE;
"""


def upgrade() -> None:
    op.get_bind().execute(text(_SQL_UP))


def downgrade() -> None:
    op.get_bind().execute(text(_SQL_DOWN))
