"""Pass 4 — objective auto-archive rules.

Two deterministic triggers:

  1. 404-streak: catalog asset whose source.url has 404'd on ≥3 consecutive
     liveness checks AND whose first 404 was >30 days ago. The 404 history
     lives in /scout/state/url-liveness.json (populated by an out-of-band
     liveness check, not by the dedup engine itself — the engine stays
     network-free).

  2. supersedes-chain: catalog asset with non-empty relations.supersedes,
     status=reviewed, and updated_at > 30 days ago.

When either trigger fires the engine writes ONLY four fields on the catalog
file: status, archived_reason, archived_at, updated_at. The body and every
other frontmatter field are left untouched.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

_THIRTY_DAYS = timedelta(days=30)
_MIN_404_STREAK = 3


def should_archive_for_404(url: str, liveness: dict, *, today: date) -> bool:
    """True iff `url` has ≥3 consecutive 404s recorded and the first 404
    happened ≥30 days before `today`."""
    if not isinstance(liveness, dict) or not isinstance(url, str) or not url:
        return False
    checks = liveness.get("checks") or {}
    entry = checks.get(url)
    if not isinstance(entry, dict):
        return False
    count = entry.get("404_count")
    first = entry.get("first_404")
    if not isinstance(count, int) or count < _MIN_404_STREAK:
        return False
    first_dt = _parse_date(first)
    if first_dt is None:
        return False
    return today - first_dt >= _THIRTY_DAYS


def should_archive_for_supersedes(fm: dict, *, today: date) -> bool:
    """True iff frontmatter has a non-empty `relations.supersedes`, `status`
    is still `reviewed`, and `updated_at` is older than 30 days."""
    if not isinstance(fm, dict):
        return False
    relations = fm.get("relations") or {}
    if not isinstance(relations, dict):
        return False
    supersedes = relations.get("supersedes") or []
    if not isinstance(supersedes, list) or not supersedes:
        return False
    if fm.get("status") != "reviewed":
        return False
    updated_d = _parse_date(fm.get("updated_at"))
    if updated_d is None:
        return False
    return today - updated_d > _THIRTY_DAYS


def _parse_date(v: object) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            return None
    return None
