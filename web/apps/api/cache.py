"""In-memory cache wrapping the indexer, with mtime-based invalidation.

v1 uses a process-local cache. Cold start: full walk (~100ms for the current
repo). Subsequent requests check the max mtime under the indexed surfaces; if
nothing has changed since the snapshot's `scan_mtime_ceiling`, we return the
cached snapshot. If anything has changed, we rebuild.

When the index becomes persistent (milestone 8.2), `CachedIndex` keeps the
same interface and swaps the storage layer underneath.
"""

from __future__ import annotations

import threading
from pathlib import Path

from .indexer import Indexer, IndexSnapshot

# Surfaces whose mtime we sample for staleness checks. These are the
# directories that actually change between requests. Walking just these dirs
# (recursively) is much cheaper than re-running the full scan.
_WATCH_DIRS = (
    "catalog",
    "scout/queue",
    "consulting/engagements",
    "conventions",
    "docs/plans",
    "docs/runbooks",
    "command-center/runbooks",
    "command-center/threads",
    "claude",
)


class CachedIndex:
    """Thread-safe wrapper around `Indexer.scan()`."""

    def __init__(self, repo_root: Path) -> None:
        self._indexer = Indexer(repo_root)
        self._lock = threading.Lock()
        self._snapshot: IndexSnapshot | None = None
        self._last_seen_mtime: float = 0.0

    @property
    def repo_root(self) -> Path:
        return self._indexer.repo_root

    def get(self) -> IndexSnapshot:
        """Return the current snapshot, rebuilding if anything has changed."""
        latest = self._latest_mtime_under_watch_dirs()
        with self._lock:
            if self._snapshot is None or latest > self._last_seen_mtime:
                self._snapshot = self._indexer.scan()
                # Use max of (latest, scan ceiling) so a same-second change
                # doesn't fool us into thinking we're stale.
                self._last_seen_mtime = max(latest, self._snapshot.scan_mtime_ceiling)
            return self._snapshot

    def force_rebuild(self) -> IndexSnapshot:
        """Skip the mtime check; rebuild now. Used by `POST /sync`."""
        with self._lock:
            self._snapshot = self._indexer.scan()
            self._last_seen_mtime = max(
                self._latest_mtime_under_watch_dirs(),
                self._snapshot.scan_mtime_ceiling,
            )
            return self._snapshot

    def _latest_mtime_under_watch_dirs(self) -> float:
        """Cheap staleness probe: max mtime of the directories themselves.

        Adding or removing a file under a directory bumps the directory's own
        mtime on POSIX, so we don't have to walk into them on every request.
        """
        latest = 0.0
        for rel in _WATCH_DIRS:
            d = self._indexer.repo_root / rel
            try:
                m = d.stat().st_mtime
                if m > latest:
                    latest = m
            except OSError:
                continue
        return latest


_cache: CachedIndex | None = None
_cache_lock = threading.Lock()


def get_cached_index(repo_root: Path) -> CachedIndex:
    """Process-singleton accessor used by FastAPI dependency injection."""
    global _cache
    with _cache_lock:
        if _cache is None or _cache.repo_root != repo_root.resolve():
            _cache = CachedIndex(repo_root)
        return _cache


def reset_cached_index() -> None:
    """Test hook — drops the singleton so the next call rebuilds."""
    global _cache
    with _cache_lock:
        _cache = None
