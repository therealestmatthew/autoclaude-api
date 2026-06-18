"""Catalog browser endpoints — the master DB of polymorphic assets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..cache import CachedIndex
from ..models import AssetDetail, ListResponse
from ..writes import editor, fs
from ._filters import filter_records, paginate
from ._serialize import to_detail, to_summary
from .deps import get_index

router = APIRouter(prefix="/catalog", tags=["catalog"])


class AssetRaw(BaseModel):
    """The exact on-disk frontmatter dict + body text + optimistic-lock
    token. Used by the editor so a save round-trips every frontmatter key,
    including ones the typed `AssetDetail` doesn't expose (e.g. fingerprint)."""

    path: str
    bucket: str
    slug: str
    frontmatter: dict
    body: str
    version: str


@router.get("", response_model=ListResponse)
def list_catalog(
    kind: str | None = Query(default=None),
    status: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Substring match on slug/title/tags."),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    index: CachedIndex = Depends(get_index),
) -> ListResponse:
    snapshot = index.get()
    records = [r for r in snapshot.records if r.bucket == "catalog"]
    filtered = filter_records(records, kind=kind, status=status, tag=tag, q=q)
    page = paginate(filtered, offset, limit)
    return ListResponse(items=[to_summary(r) for r in page], total=len(filtered))


@router.get("/{slug}", response_model=AssetDetail)
def get_catalog_asset(
    slug: str, index: CachedIndex = Depends(get_index)
) -> AssetDetail:
    snapshot = index.get()
    for r in snapshot.records:
        if r.bucket == "catalog" and r.slug == slug:
            return to_detail(r)
    raise HTTPException(status_code=404, detail=f"catalog asset not found: {slug}")


@router.get("/{slug}/raw", response_model=AssetRaw)
def get_catalog_raw(
    slug: str, index: CachedIndex = Depends(get_index)
) -> AssetRaw:
    """Return the parsed full frontmatter + body for the editor."""
    from scout._util import parse_frontmatter

    from ..writes.serialize import parse_body

    snapshot = index.get()
    record = next(
        (r for r in snapshot.records if r.bucket == "catalog" and r.slug == slug),
        None,
    )
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"catalog asset not found: {slug}"
        )
    target = fs.safe_path(index.repo_root, record.path)
    text = target.read_text(encoding="utf-8") if target.is_file() else ""
    frontmatter = parse_frontmatter(text) or {}
    body = parse_body(text)
    version = editor.current_version_for(index.repo_root, record.path)
    return AssetRaw(
        path=record.path,
        bucket="catalog",
        slug=slug,
        frontmatter=frontmatter,
        body=body,
        version=version,
    )
