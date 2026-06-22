"""Client CRUD endpoints.

Clients are lightweight DB records (not catalog assets) that carry a name,
industry, default brand, and engagement context for repeat exports.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..cache import CachedIndex
from ..db.models import Client
from ..models import ClientCreate, ClientItem, ClientListResponse, ClientUpdate
from .deps import get_index

router = APIRouter(prefix="/clients", tags=["clients"])


def _session(index: CachedIndex) -> Session:
    return index.session_factory()


def _to_item(row: Client) -> ClientItem:
    return ClientItem(
        slug=row.slug,
        name=row.name,
        industry=row.industry,
        brand_slug=row.brand_slug,
        engagement_context=row.engagement_context,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=ClientListResponse)
def list_clients(
    q: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    index: CachedIndex = Depends(get_index),
) -> ClientListResponse:
    with _session(index) as session:
        rows = session.execute(select(Client).order_by(Client.name)).scalars().all()
    if q:
        q_lower = q.lower()
        rows = [r for r in rows if q_lower in r.name.lower() or q_lower in (r.industry or "").lower()]
    total = len(rows)
    page = rows[offset : offset + limit]
    return ClientListResponse(items=[_to_item(r) for r in page], total=total)


@router.post("", response_model=ClientItem, status_code=201)
def create_client(
    body: ClientCreate,
    index: CachedIndex = Depends(get_index),
) -> ClientItem:
    now = time.time()
    with _session(index) as session:
        existing = session.get(Client, body.slug)
        if existing:
            raise HTTPException(status_code=409, detail=f"client already exists: {body.slug}")
        row = Client(
            slug=body.slug,
            name=body.name,
            industry=body.industry,
            brand_slug=body.brand_slug,
            engagement_context=body.engagement_context,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_item(row)


@router.get("/{slug}", response_model=ClientItem)
def get_client(slug: str, index: CachedIndex = Depends(get_index)) -> ClientItem:
    with _session(index) as session:
        row = session.get(Client, slug)
    if row is None:
        raise HTTPException(status_code=404, detail=f"client not found: {slug}")
    return _to_item(row)


@router.put("/{slug}", response_model=ClientItem)
def update_client(
    slug: str,
    body: ClientUpdate,
    index: CachedIndex = Depends(get_index),
) -> ClientItem:
    with _session(index) as session:
        row = session.get(Client, slug)
        if row is None:
            raise HTTPException(status_code=404, detail=f"client not found: {slug}")
        if body.name is not None:
            row.name = body.name
        if body.industry is not None:
            row.industry = body.industry
        if body.brand_slug is not None:
            row.brand_slug = body.brand_slug
        if body.engagement_context is not None:
            row.engagement_context = body.engagement_context
        row.updated_at = time.time()
        session.commit()
        session.refresh(row)
        return _to_item(row)


@router.delete("/{slug}", status_code=204)
def delete_client(slug: str, index: CachedIndex = Depends(get_index)) -> None:
    with _session(index) as session:
        row = session.get(Client, slug)
        if row is None:
            raise HTTPException(status_code=404, detail=f"client not found: {slug}")
        session.delete(row)
        session.commit()
