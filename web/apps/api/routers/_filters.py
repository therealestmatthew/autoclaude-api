"""Shared filter/sort/paginate helpers for list endpoints.

Kept tiny on purpose — query semantics live where they're used, not in a
framework. When this grows past ~100 lines we extract a real query builder.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..indexer import AssetRecord


def _sort_key(rec: AssetRecord) -> tuple[str, str]:
    """Deterministic sort: updated_at desc, then path asc as tiebreaker.

    Returned as a tuple where the first element is inverted so callers using
    `sorted(..., key=...)` without `reverse=True` get the desired order.
    """
    return (_invert_date(rec.updated_at), rec.path)


def _invert_date(d: str | None) -> str:
    """Map an ISO date to a string that sorts in reverse-chronological order.

    `9999-99-99` is greater than any real date; missing dates sort last.
    Inverting digits is a cheap trick that avoids `reverse=True` in callers
    that want secondary ascending sorts.
    """
    if not d:
        return "0000-00-00"
    digits = "9876543210"
    tr = str.maketrans("0123456789", digits)
    return d.translate(tr)


def filter_records(
    records: Iterable[AssetRecord],
    *,
    kind: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    q: str | None = None,
) -> list[AssetRecord]:
    """Apply the common list-endpoint filters in a single pass."""
    q_lower = q.lower() if q else None
    out: list[AssetRecord] = []
    for r in records:
        if kind and (r.kind or "") != kind:
            continue
        if status and (r.status or "") != status:
            continue
        if tag and tag not in r.tags:
            continue
        if q_lower:
            haystack = " ".join(
                filter(
                    None,
                    [r.slug, r.title or "", " ".join(r.tags), r.path],
                )
            ).lower()
            if q_lower not in haystack:
                continue
        out.append(r)
    return sorted(out, key=_sort_key)


def paginate(
    records: list[AssetRecord], offset: int, limit: int
) -> list[AssetRecord]:
    if offset < 0:
        offset = 0
    if limit <= 0:
        return []
    return records[offset : offset + limit]
