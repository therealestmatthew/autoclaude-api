"""Thread-log endpoints — the agentic activity feed.

Reads JSONL from `/command-center/threads/<date>.jsonl`. Files are
gitignored; the reader handles missing files gracefully (fresh checkout)
and bad lines (skip + report).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from ..cache import CachedIndex
from ..models import ThreadEvent, ThreadResponse
from .deps import get_index

router = APIRouter(prefix="/threads", tags=["threads"])

THREAD_DIR = "command-center/threads"


def _read_day(repo_root: Path, day: date) -> list[ThreadEvent]:
    path = repo_root / THREAD_DIR / f"{day.isoformat()}.jsonl"
    if not path.is_file():
        return []
    events: list[ThreadEvent] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue
        events.append(
            ThreadEvent(
                date=day.isoformat(),
                thread_id=raw.get("thread_id"),
                agent=raw.get("agent"),
                started_at=raw.get("started_at"),
                ended_at=raw.get("ended_at"),
                outcome=raw.get("outcome"),
                summary=raw.get("summary"),
                model=raw.get("model"),
                input_tokens=raw.get("input_tokens"),
                output_tokens=raw.get("output_tokens"),
                raw=raw,
            )
        )
    return events


def _parse_date(s: str | None, default: date) -> date:
    if not s:
        return default
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return default


@router.get("", response_model=ThreadResponse)
def list_threads(
    date_: str | None = Query(default=None, alias="date", description="YYYY-MM-DD"),
    since: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    until: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    agent: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    index: CachedIndex = Depends(get_index),
) -> ThreadResponse:
    repo_root = index.repo_root
    today = date.today()
    if date_:
        start = end = _parse_date(date_, today)
    else:
        start = _parse_date(since, today - timedelta(days=7))
        end = _parse_date(until, today)
    if start > end:
        start, end = end, start

    events: list[ThreadEvent] = []
    day = start
    days_scanned = 0
    while day <= end:
        events.extend(_read_day(repo_root, day))
        day += timedelta(days=1)
        days_scanned += 1

    if agent:
        events = [e for e in events if (e.agent or "") == agent]
    if outcome:
        events = [e for e in events if (e.outcome or "") == outcome]

    events.sort(key=lambda e: (e.started_at or "", e.thread_id or ""), reverse=True)
    return ThreadResponse(
        events=events[:limit],
        total=len(events),
        days_scanned=days_scanned,
    )


@router.get("/recent", response_model=ThreadResponse)
def recent_threads(
    limit: int = Query(default=50, ge=1, le=500),
    days: int = Query(default=14, ge=1, le=90),
    index: CachedIndex = Depends(get_index),
) -> ThreadResponse:
    repo_root = index.repo_root
    today = date.today()
    events: list[ThreadEvent] = []
    days_scanned = 0
    for offset in range(days):
        day = today - timedelta(days=offset)
        events.extend(_read_day(repo_root, day))
        days_scanned += 1
        if len(events) >= limit * 3:  # crude early-exit; sort handles ordering
            break
    events.sort(key=lambda e: (e.started_at or "", e.thread_id or ""), reverse=True)
    return ThreadResponse(
        events=events[:limit],
        total=len(events),
        days_scanned=days_scanned,
    )
