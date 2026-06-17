"""SQLAlchemy-backed persistence for the web command center index.

The 8.1 in-memory `CachedIndex` swaps its backing store to this module in 8.2:
the `Indexer.scan()` output drains into a relational schema (SQLite default,
Postgres-compatible) via `sync()`, and routers materialise their snapshots
via `query.load_snapshot()`.

Public surface:

- `Base`                — declarative base for migrations
- `Asset`, `IndexMeta`  — ORM models
- `make_engine`, `make_session_factory`, `resolve_dsn`
                        — engine + session bootstrap
- `sync`, `SyncResult`  — drive the indexer -> DB pipeline
- `load_snapshot`       — ORM -> `IndexSnapshot` (the in-memory shape routers
                          already speak)
- `migrations_dir`      — absolute path to the Alembic env, used by the CLI
"""

from __future__ import annotations

from .models import Asset, Base, IndexMeta
from .query import load_snapshot
from .session import make_engine, make_session_factory, migrations_dir, resolve_dsn
from .sync import SyncResult, sync

__all__ = [
    "Asset",
    "Base",
    "IndexMeta",
    "SyncResult",
    "load_snapshot",
    "make_engine",
    "make_session_factory",
    "migrations_dir",
    "resolve_dsn",
    "sync",
]
