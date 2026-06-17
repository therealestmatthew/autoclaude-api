"""Drain `Indexer.scan()` into the asset table.

The contract:

- **Idempotent.** Two runs against the same filesystem write exactly the
  rows whose content actually changed. A no-op run touches `sync_run_id`
  on every row but writes no payload columns.
- **Crash-safe.** A kill mid-sync leaves the DB in a state where the next
  sync converges. We never half-write a row (the upsert is a single
  transaction per record); a partial run merely leaves an older
  `sync_run_id` on rows we didn't reach, which the next sync replaces.
- **Pure relative to the snapshot.** The same `IndexSnapshot` always
  produces the same byte-for-byte rows. `content_hash` covers everything
  on the wire so the only allowed source of diff is real content change.

The primary key is `path` (one file -> one row, the filesystem guarantees
uniqueness). `(bucket, slug)` is a non-unique composite index — unnamed
README.md files all fall back to slug='readme' so a `(bucket, slug)` PK
would collide on real data.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from ..indexer import AssetRecord, Indexer, IndexSnapshot
from .models import Asset, IndexMeta
from .session import SCHEMA_VERSION

# Process-wide lock around sync(). The reconciler and manual operator
# invocations both write to the same DB; SQLite serialises writes at the
# file level, but our read-modify-write loop assumes a consistent view of
# `existing_by_path` across the loop. The lock turns concurrent syncs
# into a queue.
_SYNC_LOCK = threading.Lock()


@dataclass(frozen=True)
class SyncResult:
    run_id: str
    repo_root: str
    records: int
    rows_written: int
    rows_skipped: int
    rows_deleted: int
    duration_seconds: float


def _new_run_id() -> str:
    return f"sync-{int(time.time())}-{secrets.token_hex(4)}"


def _normalize_json(value: object) -> object:
    """Recursively coerce a parsed-from-YAML structure into JSON-safe shape.

    Two YAML 1.1 quirks bite us here:

    - Bare keys like `on`, `yes`, `off` parse to booleans; a `discovered:`
      block with `on: 2026-06-15` ends up as `{True: date(...)}`. JSON sorting
      and SQLAlchemy's default JSON encoder both choke on that.
    - ISO date values parse to `datetime.date`, which is also not JSON-native.

    Coerce keys to strings and date/datetime values to ISO strings. Other
    types pass through.
    """
    if isinstance(value, dict):
        return {str(k): _normalize_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_json(v) for v in value]
    if isinstance(value, tuple):
        return [_normalize_json(v) for v in value]
    if hasattr(value, "isoformat") and not isinstance(value, str):
        # Handles datetime.date / datetime.datetime; ducks anything else
        # custom that exposes the same shape.
        try:
            return value.isoformat()  # type: ignore[call-arg]
        except Exception:
            return str(value)
    return value


def _stable_json(value: object) -> str:
    """Sort-keyed JSON dump so the hash doesn't depend on dict insertion order."""
    return json.dumps(
        _normalize_json(value), sort_keys=True, separators=(",", ":")
    )


def _hash_record(rec: AssetRecord) -> str:
    """SHA-256 over everything that ends up on the wire.

    Notably excludes `mtime` — an mtime-only change (e.g. `touch`) should
    not cause a write. This matches the 8.1 watch-dir cache intent.
    """
    payload = _stable_json(
        {
            "path": rec.path,
            "bucket": rec.bucket,
            "slug": rec.slug,
            "kind": rec.kind,
            "title": rec.title,
            "status": rec.status,
            "quality": rec.quality,
            "tags": list(rec.tags),
            "source": rec.source,
            "discovered": rec.discovered,
            "relations": rec.relations,
            "issues": list(rec.issues),
            "created_at": rec.created_at,
            "updated_at": rec.updated_at,
            "body": rec.body,
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _existing_by_path(session: Session) -> dict[str, Asset]:
    rows = session.execute(select(Asset)).scalars().all()
    return {row.path: row for row in rows}


def _apply_record(row: Asset, rec: AssetRecord, content_hash: str, run_id: str) -> None:
    """Copy record fields onto an existing or freshly-constructed row."""
    row.path = rec.path
    row.bucket = rec.bucket
    row.slug = rec.slug
    row.kind = rec.kind
    row.title = rec.title
    row.status = rec.status
    row.quality = rec.quality
    row.tags = list(rec.tags)
    row.source = _normalize_json(rec.source) if rec.source is not None else None
    row.discovered = (
        _normalize_json(rec.discovered) if rec.discovered is not None else None
    )
    row.relations = (
        _normalize_json(rec.relations) if rec.relations is not None else None
    )
    row.issues = list(rec.issues)
    row.created_at = rec.created_at
    row.updated_at = rec.updated_at
    row.mtime = rec.mtime
    row.body = rec.body
    row.content_hash = content_hash
    row.sync_run_id = run_id


def _stamp_meta(
    session: Session, snapshot: IndexSnapshot, run_id: str, repo_root: Path
) -> None:
    meta = session.get(IndexMeta, 1)
    if meta is None:
        meta = IndexMeta(id=1)
        session.add(meta)
    meta.repo_root = repo_root.resolve().as_posix()
    meta.last_sync_at = time.time()
    meta.last_sync_run_id = run_id
    meta.last_sync_record_count = len(snapshot.records)
    meta.schema_version = SCHEMA_VERSION


def sync(
    indexer: Indexer,
    session_factory: sessionmaker[Session],
    *,
    run_id: str | None = None,
) -> SyncResult:
    """Drain `indexer.scan()` into the DB. See module docstring for the
    invariants this respects."""

    started = time.perf_counter()
    snapshot = indexer.scan()
    run_id = run_id or _new_run_id()

    rows_written = 0
    rows_skipped = 0
    rows_deleted = 0

    with _SYNC_LOCK, session_factory() as session, session.begin():
        existing = _existing_by_path(session)
        seen_paths: set[str] = set()

        for rec in snapshot.records:
            new_hash = _hash_record(rec)
            seen_paths.add(rec.path)

            row = existing.get(rec.path)
            if row is None:
                row = Asset()
                _apply_record(row, rec, new_hash, run_id)
                session.add(row)
                rows_written += 1
                continue

            if row.content_hash == new_hash:
                # No-op for the data columns; just stamp the run id so
                # reconciliation doesn't delete us. Single-column update.
                row.sync_run_id = run_id
                rows_skipped += 1
                continue

            _apply_record(row, rec, new_hash, run_id)
            rows_written += 1

        # Reconciliation: anything we didn't touch is stale.
        stale_paths = [p for p in existing if p not in seen_paths]
        if stale_paths:
            session.execute(delete(Asset).where(Asset.path.in_(stale_paths)))
            rows_deleted += len(stale_paths)

        _stamp_meta(session, snapshot, run_id, indexer.repo_root)

    duration = time.perf_counter() - started
    return SyncResult(
        run_id=run_id,
        repo_root=indexer.repo_root.as_posix(),
        records=len(snapshot.records),
        rows_written=rows_written,
        rows_skipped=rows_skipped,
        rows_deleted=rows_deleted,
        duration_seconds=duration,
    )
