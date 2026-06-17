"""Scout queue endpoints — candidates pending human review."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..cache import CachedIndex
from ..models import AssetDetail, ListResponse
from ._filters import filter_records, paginate
from ._serialize import to_detail, to_summary
from .deps import get_index

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("", response_model=ListResponse)
def list_queue(
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    index: CachedIndex = Depends(get_index),
) -> ListResponse:
    snapshot = index.get()
    records = [r for r in snapshot.records if r.bucket == "queue"]
    filtered = filter_records(records, kind=kind, q=q)
    page = paginate(filtered, offset, limit)
    return ListResponse(items=[to_summary(r) for r in page], total=len(filtered))


@router.get("/{slug}", response_model=AssetDetail)
def get_queue_candidate(
    slug: str, index: CachedIndex = Depends(get_index)
) -> AssetDetail:
    snapshot = index.get()
    for r in snapshot.records:
        if r.bucket == "queue" and r.slug == slug:
            return to_detail(r)
    raise HTTPException(status_code=404, detail=f"queue candidate not found: {slug}")
