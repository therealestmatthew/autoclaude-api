"""DB-backed read snapshot for the routers.

The 8.1 API was an in-process dict invalidated by directory mtime. 8.2 keeps
the same `CachedIndex.get() -> IndexSnapshot` shape, but the snapshot is
materialised by `db.query.load_snapshot()` from the SQLite/Postgres tables.
A per-request snapshot is cheap enough at v1 scale (~500 rows × a few KB
each); if profiling pushes back we add a meta-mtime-keyed in-process cache
behind this interface.

`force_rebuild()` drives a full sync (`Indexer.scan()` -> upserts) and
returns the resulting snapshot. The `POST /sync` endpoint and tests use it.
"""

from __future__ import annotations

import threading
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from .db import (
    SyncResult,
    load_snapshot,
    make_engine,
    make_session_factory,
    resolve_dsn,
    sync,
)
from .indexer import Indexer, IndexSnapshot


class CachedIndex:
    """Same interface 8.1 exposed; storage swapped to the DB."""

    def __init__(
        self,
        repo_root: Path,
        *,
        engine: Engine | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._repo_root = repo_root.resolve()
        if engine is None:
            engine = make_engine(resolve_dsn(self._repo_root))
        if session_factory is None:
            session_factory = make_session_factory(engine)
        self._engine = engine
        self._session_factory = session_factory

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def session_factory(self) -> sessionmaker[Session]:
        return self._session_factory

    def get(self) -> IndexSnapshot:
        """Materialise the current snapshot from the DB."""
        return load_snapshot(self._session_factory, self._repo_root.as_posix())

    def force_rebuild(self) -> IndexSnapshot:
        """Drive a full sync, then return the new snapshot."""
        sync(Indexer(self._repo_root), self._session_factory)
        return self.get()

    def sync(self) -> SyncResult:
        """Run a sync without immediately materialising a snapshot. The
        polling reconciler uses this so it doesn't pay the snapshot cost."""
        return sync(Indexer(self._repo_root), self._session_factory)


_cache: CachedIndex | None = None
_cache_lock = threading.Lock()


def get_cached_index(repo_root: Path) -> CachedIndex:
    """Process-singleton accessor used by FastAPI dependency injection."""
    global _cache
    resolved = repo_root.resolve()
    with _cache_lock:
        if _cache is None or _cache.repo_root != resolved:
            _cache = CachedIndex(resolved)
        return _cache


def reset_cached_index() -> None:
    """Test hook — drops the singleton so the next call rebuilds with the
    next process's repo_root + DSN."""
    global _cache
    with _cache_lock:
        _cache = None
