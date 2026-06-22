"""Timeline endpoints — markdown-backed customizable calendars.

A timeline file lives at /timelines/<slug>.md with `kind: timeline` and an
`entries:` list in its frontmatter. The indexer registers each as a row in
the 'timeline' bucket; this router re-reads the file to expose the full
entries list (which the indexer doesn't preserve on AssetRecord).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from scout._util import parse_frontmatter

from ..cache import CachedIndex
from ..indexer import AssetRecord
from ..models import (
    TimelineDetail,
    TimelineEntry,
    TimelineListResponse,
    TimelineSummary,
)
from .deps import get_index

router = APIRouter(prefix="/timelines", tags=["timelines"])


def _coerce_entries(raw: object) -> list[TimelineEntry]:
    if not isinstance(raw, list):
        return []
    out: list[TimelineEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        clean = {
            k: (str(v) if hasattr(v, "isoformat") and callable(v.isoformat) and not isinstance(v, str) else v)
            for k, v in item.items()
            if v is not None
        }
        for date_key in ("date", "start", "end"):
            v = clean.get(date_key)
            if hasattr(v, "isoformat") and callable(v.isoformat):
                clean[date_key] = v.isoformat()
        try:
            out.append(TimelineEntry(**clean))
        except ValidationError:
            continue
    return out


def _entry_sort_key(e: TimelineEntry) -> str:
    return e.date or e.start or e.end or "9999-12-31"


def _summary_from_record_and_entries(
    rec: AssetRecord, entries: list[TimelineEntry], view: str
) -> TimelineSummary:
    sorted_entries = sorted(entries, key=_entry_sort_key)
    first = sorted_entries[0] if sorted_entries else None
    last = sorted_entries[-1] if sorted_entries else None
    return TimelineSummary(
        path=rec.path,
        slug=rec.slug,
        title=rec.title,
        status=rec.status,
        view=view,
        entry_count=len(entries),
        first_date=_entry_sort_key(first) if first else None,
        last_date=_entry_sort_key(last) if last else None,
        tags=list(rec.tags),
    )


def _load_entries_for(rec: AssetRecord, index: CachedIndex) -> tuple[list[TimelineEntry], str, str]:
    """Re-read the file to pull entries out of frontmatter."""
    abs_path = (Path(index.repo_root) / rec.path).resolve()
    repo_root = Path(index.repo_root).resolve()
    try:
        abs_path.relative_to(repo_root)  # guard: must be inside repo
    except ValueError:
        raise HTTPException(status_code=404, detail=f"timeline not found: {rec.slug}")
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail=f"timeline not found: {rec.slug}")

    text = abs_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text) or {}
    entries = _coerce_entries(fm.get("entries"))
    view_raw = fm.get("view")
    view = view_raw if isinstance(view_raw, str) and view_raw in {"list", "month"} else "list"

    body = ""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            body = parts[2].lstrip("\n")
    return entries, view, body


@router.get("", response_model=TimelineListResponse)
def list_timelines(index: CachedIndex = Depends(get_index)) -> TimelineListResponse:
    snapshot = index.get()
    records = [r for r in snapshot.records if r.bucket == "timeline"]
    items: list[TimelineSummary] = []
    for rec in records:
        try:
            entries, view, _body = _load_entries_for(rec, index)
        except HTTPException:
            continue
        items.append(_summary_from_record_and_entries(rec, entries, view))
    items.sort(key=lambda s: (s.title or s.slug).lower())
    return TimelineListResponse(items=items, total=len(items))


@router.get("/{slug}", response_model=TimelineDetail)
def get_timeline(slug: str, index: CachedIndex = Depends(get_index)) -> TimelineDetail:
    snapshot = index.get()
    rec = next(
        (r for r in snapshot.records if r.bucket == "timeline" and r.slug == slug),
        None,
    )
    if rec is None:
        raise HTTPException(status_code=404, detail=f"timeline not found: {slug}")

    entries, view, body = _load_entries_for(rec, index)
    summary = _summary_from_record_and_entries(rec, entries, view)
    sorted_entries = sorted(entries, key=_entry_sort_key)
    return TimelineDetail(
        **summary.model_dump(),
        body=body,
        entries=sorted_entries,
    )
