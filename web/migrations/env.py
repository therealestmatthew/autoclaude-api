"""Alembic env.py for the ft-autoclaude web persistent index.

Supports offline (`alembic upgrade --sql`) and online runs. The DSN is
injected via `config.set_main_option("sqlalchemy.url", ...)` by the CLI
before `command.upgrade(...)` runs; falling back to the ini value if
present, then to the env var, makes the env usable from a bare `alembic`
invocation in a tight loop.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `web.apps.api.db` importable without depending on PYTHONPATH or `uv`
# (alembic may be invoked directly during development).
_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from web.apps.api.db.models import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _dsn() -> str:
    """Resolve a DSN for the migration run."""
    if (cli_url := config.get_main_option("sqlalchemy.url")):
        return cli_url
    env_url = os.environ.get("FT_AUTOCLAUDE_INDEX_DSN", "").strip()
    if env_url:
        return env_url
    raise RuntimeError(
        "alembic env: no DSN provided. Set sqlalchemy.url in alembic.ini, "
        "FT_AUTOCLAUDE_INDEX_DSN, or call via ft-autoclaude-index."
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_dsn(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _dsn()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # `render_as_batch=True` lets SQLite handle ALTER TABLE shapes
        # (column drops, type changes) by recreating the table behind the
        # scenes. Harmless on Postgres.
        is_sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
