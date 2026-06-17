"""Cross-bucket search — slug, title, tags, body."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..cache import CachedIndex
from ..indexer import AssetRecord
from ..models import SearchHit, SearchResponse
from .deps import get_index

router = APIRouter(tags=["search"])


def _score(rec: AssetRecord, q: str) -> tuple[float, list[str]]:
    """Coarse scoring: slug/title hits weighted highest, then tags, then body.

    Returns (score, matched_fields). Score is 0.0 if nothing matched.
    """
    q_lower = q.lower()
    if not q_lower:
        return 0.0, []
    score = 0.0
    matched: list[str] = []
    if q_lower in rec.slug.lower():
        score += 5.0
        matched.append("slug")
    if rec.title and q_lower in rec.title.lower():
        score += 4.0
        matched.append("title")
    if any(q_lower in t.lower() for t in rec.tags):
        score += 2.0
        matched.append("tags")
    if q_lower in rec.body.lower():
        score += 1.0
        matched.append("body")
    return score, matched


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1, max_length=200),
    bucket: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    index: CachedIndex = Depends(get_index),
) -> SearchResponse:
    snapshot = index.get()
    hits: list[SearchHit] = []
    for r in snapshot.records:
        if bucket and r.bucket != bucket:
            continue
        score, matched = _score(r, q)
        if score <= 0.0:
            continue
        hits.append(
            SearchHit(
                path=r.path,
                bucket=r.bucket,
                slug=r.slug,
                kind=r.kind,
                title=r.title,
                status=r.status,
                quality=r.quality,
                tags=list(r.tags),
                created_at=r.created_at,
                updated_at=r.updated_at,
                issues=list(r.issues),
                score=score,
                matched=matched,
            )
        )
    hits.sort(key=lambda h: (-h.score, h.path))
    return SearchResponse(query=q, hits=hits[:limit], total=len(hits))
