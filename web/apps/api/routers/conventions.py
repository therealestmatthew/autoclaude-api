"""Conventions and plans — the rules and the design lineage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..cache import CachedIndex
from ..models import AssetDetail, ListResponse
from ._filters import filter_records
from ._serialize import to_detail, to_summary
from .deps import get_index

router = APIRouter(tags=["docs"])


@router.get("/conventions", response_model=ListResponse)
def list_conventions(index: CachedIndex = Depends(get_index)) -> ListResponse:
    snapshot = index.get()
    records = [r for r in snapshot.records if r.bucket == "convention"]
    sorted_records = filter_records(records)
    return ListResponse(
        items=[to_summary(r) for r in sorted_records], total=len(sorted_records)
    )


@router.get("/conventions/{slug}", response_model=AssetDetail)
def get_convention(slug: str, index: CachedIndex = Depends(get_index)) -> AssetDetail:
    snapshot = index.get()
    for r in snapshot.records:
        if r.bucket == "convention" and r.slug == slug:
            return to_detail(r)
    raise HTTPException(status_code=404, detail=f"convention not found: {slug}")


@router.get("/plans", response_model=ListResponse)
def list_plans(index: CachedIndex = Depends(get_index)) -> ListResponse:
    snapshot = index.get()
    records = [r for r in snapshot.records if r.bucket == "plan"]
    sorted_records = filter_records(records)
    return ListResponse(
        items=[to_summary(r) for r in sorted_records], total=len(sorted_records)
    )


@router.get("/plans/{slug}", response_model=AssetDetail)
def get_plan(slug: str, index: CachedIndex = Depends(get_index)) -> AssetDetail:
    snapshot = index.get()
    for r in snapshot.records:
        if r.bucket == "plan" and r.slug == slug:
            return to_detail(r)
    raise HTTPException(status_code=404, detail=f"plan not found: {slug}")
