"""Alembic migrations roundtrip cleanly against SQLite.

The same env.py drives Postgres deploys in 8.5. SQLite roundtrip here
catches "the migration only worked because SQLAlchemy's `create_all`
massaged something" — only `alembic upgrade head` runs the migration
file's exact DDL.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from web.apps.api.db.session import make_engine, migrations_dir


def _config(dsn: str) -> Config:
    cfg = Config(str(migrations_dir() / "alembic.ini"))
    cfg.set_main_option("script_location", str(migrations_dir()))
    cfg.set_main_option("sqlalchemy.url", dsn)
    return cfg


def test_upgrade_creates_tables(tmp_path: Path) -> None:
    dsn = f"sqlite:///{(tmp_path / 'i.sqlite').as_posix()}"
    command.upgrade(_config(dsn), "head")
    engine = make_engine(dsn)
    tables = set(inspect(engine).get_table_names())
    assert {"asset", "index_meta", "alembic_version"}.issubset(tables)


def test_downgrade_then_upgrade(tmp_path: Path) -> None:
    dsn = f"sqlite:///{(tmp_path / 'i.sqlite').as_posix()}"
    cfg = _config(dsn)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = make_engine(dsn)
    tables = set(inspect(engine).get_table_names())
    assert "asset" not in tables
    assert "index_meta" not in tables
    command.upgrade(cfg, "head")
    tables = set(inspect(make_engine(dsn)).get_table_names())
    assert {"asset", "index_meta"}.issubset(tables)
