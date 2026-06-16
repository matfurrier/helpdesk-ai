"""Add helpdesk.departments, helpdesk.applications and helpdesk.user_applications tables.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision: str = "0009"
down_revision: str = "0008"
branch_labels = None
depends_on = None

_SQL_UP = """
CREATE TABLE helpdesk.departments (
    id         SERIAL PRIMARY KEY,
    uuid       UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    name       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE helpdesk.applications (
    id          SERIAL PRIMARY KEY,
    app_name    TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE helpdesk.user_applications (
    id        SERIAL PRIMARY KEY,
    user_uuid TEXT NOT NULL,
    app_id    INTEGER NOT NULL REFERENCES helpdesk.applications(id) ON DELETE CASCADE,
    UNIQUE(user_uuid, app_id)
);

CREATE INDEX ix_user_applications_app  ON helpdesk.user_applications (app_id);
CREATE INDEX ix_user_applications_user ON helpdesk.user_applications (user_uuid);

CREATE TRIGGER tg_departments_updated
    BEFORE UPDATE ON helpdesk.departments
    FOR EACH ROW EXECUTE FUNCTION helpdesk.tg_set_updated_at();

CREATE TRIGGER tg_applications_updated
    BEFORE UPDATE ON helpdesk.applications
    FOR EACH ROW EXECUTE FUNCTION helpdesk.tg_set_updated_at();
"""

_SQL_DOWN = """
DROP TABLE IF EXISTS helpdesk.user_applications CASCADE;
DROP TABLE IF EXISTS helpdesk.applications CASCADE;
DROP TABLE IF EXISTS helpdesk.departments CASCADE;
"""


def upgrade() -> None:
    op.get_bind().execute(text(_SQL_UP))


def downgrade() -> None:
    op.get_bind().execute(text(_SQL_DOWN))
