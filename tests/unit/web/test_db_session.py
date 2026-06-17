"""Tests for DSN resolution and engine/session factories."""

from __future__ import annotations

from pathlib import Path

from web.apps.api.db.session import make_engine, make_session_factory, resolve_dsn


def test_resolve_dsn_default_creates_parent(tmp_path: Path) -> None:
    dsn = resolve_dsn(tmp_path, env={})
    assert dsn.startswith("sqlite:///")
    assert (tmp_path / "web" / ".data").is_dir()


def test_resolve_dsn_honours_env_override(tmp_path: Path) -> None:
    override = "postgresql+psycopg://localhost/index"
    dsn = resolve_dsn(tmp_path, env={"AUTOCLAUDE_INDEX_DSN": override})
    assert dsn == override
    # Crucially: the default SQLite parent is NOT created on override.
    assert not (tmp_path / "web" / ".data").exists()


def test_make_engine_and_session_factory_round_trip(tmp_path: Path) -> None:
    dsn = f"sqlite:///{(tmp_path / 'x.sqlite').as_posix()}"
    engine = make_engine(dsn)
    factory = make_session_factory(engine)
    # A trivial session is enough to confirm the wiring.
    with factory() as session:
        result = session.execute(__import__("sqlalchemy").text("select 1"))
        assert result.scalar_one() == 1
