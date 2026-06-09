"""Alembic environment — uses sync psycopg2 for DDL migrations.

The app runtime uses asyncpg; Alembic uses psycopg2 (sync) because asyncpg
does not support multi-statement SQL strings in a single execute() call,
which is the pattern used for the hand-authored 0001 migration.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Convert asyncpg URL to psycopg2 for Alembic's sync engine
_sync_url = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
).replace(
    "postgresql://", "postgresql+psycopg2://"
)
config.set_main_option("sqlalchemy.url", _sync_url)

target_metadata = None  # hand-authored migration, no autogenerate needed


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_sync_url, poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
