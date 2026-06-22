"""Business process taxonomy endpoints (read-only).

The business_process table is seeded by migration 0003 with the standard
finance-transformation process areas (O2C, R2R, P2P, etc.).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from ..cache import CachedIndex
from ..db.models import BusinessProcess
from ..models import BusinessProcessItem, BusinessProcessListResponse
from .deps import get_index

router = APIRouter(prefix="/processes", tags=["processes"])


def _to_item(row: BusinessProcess) -> BusinessProcessItem:
    return BusinessProcessItem(
        slug=row.slug,
        name=row.name,
        parent_slug=row.parent_slug,
        description=row.description,
    )


@router.get("", response_model=BusinessProcessListResponse)
def list_processes(
    q: str | None = Query(default=None),
    index: CachedIndex = Depends(get_index),
) -> BusinessProcessListResponse:
    with index.session_factory() as session:
        rows = session.execute(select(BusinessProcess).order_by(BusinessProcess.name)).scalars().all()
    if q:
        q_lower = q.lower()
        rows = [r for r in rows if q_lower in r.name.lower() or q_lower in (r.description or "").lower()]
    return BusinessProcessListResponse(items=[_to_item(r) for r in rows], total=len(rows))


@router.get("/{slug}", response_model=BusinessProcessItem)
def get_process(slug: str, index: CachedIndex = Depends(get_index)) -> BusinessProcessItem:
    with index.session_factory() as session:
        row = session.get(BusinessProcess, slug)
    if row is None:
        raise HTTPException(status_code=404, detail=f"process not found: {slug}")
    return _to_item(row)
