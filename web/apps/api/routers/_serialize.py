"""Helpers that convert `AssetRecord` dataclasses to Pydantic API models.

Routers should never construct `AssetSummary` / `AssetDetail` directly — go
through these helpers so the conversion stays in one place.
"""

from __future__ import annotations

from ..indexer import AssetRecord
from ..models import AssetDetail, AssetSummary


def to_summary(rec: AssetRecord) -> AssetSummary:
    return AssetSummary(
        path=rec.path,
        bucket=rec.bucket,
        slug=rec.slug,
        kind=rec.kind,
        title=rec.title,
        status=rec.status,
        quality=rec.quality,
        tags=list(rec.tags),
        delivery_functions=list(rec.delivery_functions),
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        issues=list(rec.issues),
        version=rec.raw_hash,
    )


def to_detail(rec: AssetRecord) -> AssetDetail:
    return AssetDetail(
        path=rec.path,
        bucket=rec.bucket,
        slug=rec.slug,
        kind=rec.kind,
        title=rec.title,
        status=rec.status,
        quality=rec.quality,
        tags=list(rec.tags),
        delivery_functions=list(rec.delivery_functions),
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        issues=list(rec.issues),
        version=rec.raw_hash,
        body=rec.body,
        source=rec.source,
        discovered=rec.discovered,
        relations=rec.relations,
    )
