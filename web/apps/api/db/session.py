"""Engine + session factory + DSN resolution.

The DSN defaults to SQLite at `web/.data/index.sqlite` under the configured
repo root. `AUTOCLAUDE_INDEX_DSN` overrides it. The parent directory is
auto-created so a fresh checkout's first `autoclaude-index sync` works
without manual setup.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

SCHEMA_VERSION = "0001"
"""Current Alembic head revision. The sync engine writes this into
`IndexMeta.schema_version`; tools/index.py compares it on startup."""

_DEFAULT_REL_PATH = "web/.data/index.sqlite"


def resolve_dsn(repo_root: Path, *, env: dict[str, str] | None = None) -> str:
    """Pick the DSN, ensuring the SQLite parent directory exists.

    Priority:

    1. `AUTOCLAUDE_INDEX_DSN` env var if set and non-empty.
    2. `sqlite:///<repo_root>/web/.data/index.sqlite`.

    For the SQLite default, the parent directory is created if absent.
    For overridden DSNs the caller is responsible for making the target
    reachable; we don't try to mkdir an arbitrary path.
    """
    env = env if env is not None else dict(os.environ)
    override = env.get("AUTOCLAUDE_INDEX_DSN", "").strip()
    if override:
        return override

    default_path = (repo_root / _DEFAULT_REL_PATH).resolve()
    default_path.parent.mkdir(parents=True, exist_ok=True)
    # SQLAlchemy's sqlite URL wants three slashes for an absolute path on
    # POSIX (sqlite:///abs/path). Path.as_posix() already drops the leading
    # slash semantics into the third position naturally.
    return f"sqlite:///{default_path.as_posix()}"


def make_engine(dsn: str) -> Engine:
    """Construct a SQLAlchemy engine for the given DSN.

    SQLite gets `check_same_thread=False` so the reconciler coroutine can
    share the engine with the request-handling threads (FastAPI runs handlers
    on a threadpool by default). Postgres / other DSNs pass through.
    """
    connect_args: dict[str, object] = {}
    if dsn.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(dsn, connect_args=connect_args, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Standard sessionmaker. `expire_on_commit=False` so callers can use
    objects after a commit without a refresh round-trip."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def migrations_dir() -> Path:
    """Absolute path to the Alembic env. Used by the CLI and tests."""
    return (Path(__file__).resolve().parents[3] / "migrations").resolve()
