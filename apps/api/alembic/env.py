"""Alembic environment.

Runs against the *sync* driver (psycopg) even though the application uses
asyncpg. Migrations are a one-shot administrative task; an async engine buys
nothing here and complicates `alembic upgrade` inside an entrypoint script.

`compare_type` and `compare_server_default` are on so autogenerate notices a
column widening or a changed default — the drift that otherwise only surfaces
as a production insert failure.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401 - registers every mapper on Base.metadata
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC")
    if not url:
        # Fall back to the async URL with the driver swapped, so `make migrate`
        # works from a plain .env without a second variable.
        async_url = os.environ.get("DATABASE_URL", "")
        url = async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    if not url:
        raise RuntimeError("Set DATABASE_URL_SYNC (or DATABASE_URL) before running Alembic.")
    return url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a connection — used to review a change set."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Every migration runs in one transaction: a failure halfway
            # through leaves the schema untouched rather than half-applied.
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
