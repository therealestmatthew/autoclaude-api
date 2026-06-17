"""ORM -> `IndexSnapshot` materialiser.

The 8.1 cache returned an `IndexSnapshot` of `AssetRecord`s. The router code
(filters, paginators, serializers) is written against that shape; 8.2 keeps
that shape and produces it from the DB on demand.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..indexer import AssetRecord, IndexSnapshot
from .models import Asset, IndexMeta


def _row_to_record(row: Asset) -> AssetRecord:
    return AssetRecord(
        path=row.path,
        bucket=row.bucket,  # type: ignore[arg-type]
        slug=row.slug,
        kind=row.kind,
        title=row.title,
        status=row.status,
        quality=row.quality,
        tags=tuple(row.tags or ()),
        source=row.source,
        discovered=row.discovered,
        relations=row.relations,
        created_at=row.created_at,
        updated_at=row.updated_at,
        body=row.body or "",
        issues=tuple(row.issues or ()),
        mtime=row.mtime,
    )


def load_snapshot(session_factory: sessionmaker[Session], repo_root: str) -> IndexSnapshot:
    """Build an `IndexSnapshot` from the current asset table contents."""
    with session_factory() as session:
        rows = (
            session.execute(select(Asset).order_by(Asset.path)).scalars().all()
        )
        records = [_row_to_record(r) for r in rows]
        meta = session.get(IndexMeta, 1)
        ceiling = meta.last_sync_at if meta is not None else 0.0

    return IndexSnapshot(
        records=records,
        scan_mtime_ceiling=ceiling,
        repo_root=repo_root,
    )
