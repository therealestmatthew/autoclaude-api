"""URL liveness HEAD-er + state writer.

State shape (consumed by `scout.dedup.archive.should_archive_for_404`):

    {
      "checks": {
        "<url>": {
          "404_count": int,
          "first_404": "YYYY-MM-DD" | null,
          "last_check": "YYYY-MM-DD",
          "last_status": int | null,
          "last_error": str | null
        }
      }
    }

Rules:

- Only HEAD URLs the catalog still references (so stale entries fall off
  naturally; never garbage-collect aggressively).
- One HEAD per URL per run.
- 4xx (400-499) increments `404_count`; the *first* such 4xx in a streak
  sets `first_404`. Any 2xx / 3xx resets `404_count` to 0 and clears
  `first_404`.
- 5xx, network errors, or `UnsafeURLError` are recorded as `last_error`
  but never move the streak. The catalog keeps benefit-of-the-doubt on
  transient failures.
- Idempotent: a second run on the same status updates only `last_check`.

The HEAD wrapper is a sibling to `scout._security.safe_get_bytes` — same
URL allowlist, same redirect re-check, smaller surface.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from .._security import UnsafeURLError, safe_external_url
from .._util import parse_frontmatter

LIVENESS_STATE_FILENAME = "url-liveness.json"
DEFAULT_MAX_URLS_PER_RUN = 50


def safe_head(client: httpx.Client, url: str) -> httpx.Response:
    """URL-validated HEAD. Mirrors `safe_get_bytes` minus the streaming body.

    Raises `UnsafeURLError` if the URL fails `safe_external_url` either
    pre-request or after redirect. Other httpx exceptions propagate to
    callers, which record them as `last_error` and continue.
    """
    if not safe_external_url(url):
        raise UnsafeURLError(url)
    resp = client.head(url)
    final_url = str(resp.url)
    if not safe_external_url(final_url):
        raise UnsafeURLError(f"redirect to {final_url}")
    return resp


def _load_state(state_path: Path) -> dict[str, Any]:
    """Load `url-liveness.json`; if corrupt, back up and start fresh."""
    if not state_path.exists():
        return {"checks": {}}
    try:
        loaded = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        backup = state_path.with_suffix(f".json.broken-{ts}")
        state_path.rename(backup)
        return {"checks": {}}
    if not isinstance(loaded, dict) or not isinstance(loaded.get("checks"), dict):
        return {"checks": {}}
    return loaded


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    # Sort keys for deterministic file contents (so two identical runs
    # produce byte-identical state files).
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def _catalog_urls(catalog_dir: Path) -> list[str]:
    """Every `source.url` referenced by a top-level catalog asset, in slug order."""
    urls: list[str] = []
    if not catalog_dir.exists():
        return urls
    seen: set[str] = set()
    for md_path in sorted(catalog_dir.glob("*.md")):
        try:
            fm = parse_frontmatter(md_path.read_text())
        except OSError:
            continue
        src = fm.get("source") if isinstance(fm, dict) else None
        if not isinstance(src, dict):
            continue
        url = src.get("url")
        if isinstance(url, str) and url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _should_check(
    entry: dict[str, Any] | None,
    *,
    today: date,
    since: date | None,
) -> bool:
    """`--since` semantics: skip a URL whose last_check is newer than `since`.

    No prior entry → always check. No `--since` → always check.
    """
    if since is None or not isinstance(entry, dict):
        return True
    last = entry.get("last_check")
    if not isinstance(last, str):
        return True
    try:
        last_d = date.fromisoformat(last)
    except ValueError:
        return True
    return last_d < since


def _update_entry_for_status(
    entry: dict[str, Any],
    *,
    status: int,
    today: date,
) -> None:
    """Apply the streak rules in-place.

    Idempotency contract from the plan: "running twice in a row updates
    `last_check` but the `404_count` / `first_404` only move on actual
    status change." Concretely: if we already recorded this same status
    for this URL today, do not move the streak counters again. New day
    OR new status → apply streak math.
    """
    prev_status = entry.get("last_status")
    prev_check = entry.get("last_check")
    same_day_same_status = (
        prev_check == today.isoformat() and prev_status == status
    )
    entry["last_check"] = today.isoformat()
    entry["last_status"] = status
    entry["last_error"] = None
    if same_day_same_status:
        return
    if 400 <= status < 500:
        count = entry.get("404_count")
        # If the previous status was a 2xx/3xx, treat this as a fresh streak.
        if isinstance(prev_status, int) and 200 <= prev_status < 400:
            count = 0
            entry["first_404"] = None
        count = count + 1 if isinstance(count, int) else 1
        entry["404_count"] = count
        if entry.get("first_404") is None:
            entry["first_404"] = today.isoformat()
    elif 200 <= status < 400:
        entry["404_count"] = 0
        entry["first_404"] = None
    # 5xx (and anything outside 200-499): leave streak fields alone.


def _update_entry_for_error(
    entry: dict[str, Any],
    *,
    error: str,
    today: date,
) -> None:
    entry["last_check"] = today.isoformat()
    entry["last_error"] = error
    # Leave 404_count / first_404 untouched: transient failures don't move it.


def check_urls_once(
    catalog_dir: Path,
    state_path: Path,
    *,
    since: date | None = None,
    max_urls: int | None = DEFAULT_MAX_URLS_PER_RUN,
    client: httpx.Client | None = None,
    today: date | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """HEAD every catalog `source.url`, write the state file, return stats.

    Args:
        catalog_dir: `/catalog/`.
        state_path: `/scout/state/url-liveness.json`.
        since: skip URLs whose `last_check` is on or after this date. `None`
            means check every URL.
        max_urls: hard cap on URLs HEADed in one call. `None` means no cap.
        client: optional pre-built httpx Client (tests inject a MockTransport).
        today: optional date override (tests pin determinism).
        verbose: print per-URL status to stdout.

    Returns:
        Stats dict with `checked`, `ok`, `error_4xx`, `error_5xx`,
        `network_errors`, `unsafe`, `skipped_throttle`, and `total_urls`.
    """
    today = today or date.today()
    state = _load_state(state_path)
    checks = state["checks"]

    stats: dict[str, Any] = {
        "checked": 0,
        "ok": 0,
        "error_4xx": 0,
        "error_5xx": 0,
        "network_errors": 0,
        "unsafe": 0,
        "skipped_throttle": 0,
        "total_urls": 0,
    }

    catalog_urls = _catalog_urls(catalog_dir)
    stats["total_urls"] = len(catalog_urls)

    owns_client = client is None
    http = client or httpx.Client(
        timeout=httpx.Timeout(10.0),
        follow_redirects=True,
    )

    try:
        for url in catalog_urls:
            if max_urls is not None and stats["checked"] >= max_urls:
                break
            entry = checks.get(url) or {}
            if not _should_check(entry, today=today, since=since):
                stats["skipped_throttle"] += 1
                continue

            try:
                resp = safe_head(http, url)
                status = int(resp.status_code)
                _update_entry_for_status(entry, status=status, today=today)
                if 400 <= status < 500:
                    stats["error_4xx"] += 1
                elif status >= 500:
                    stats["error_5xx"] += 1
                else:
                    stats["ok"] += 1
                if verbose:
                    print(f"[liveness] {status} {url}")
            except UnsafeURLError as e:
                _update_entry_for_error(entry, error=f"unsafe-url: {e}", today=today)
                stats["unsafe"] += 1
                if verbose:
                    print(f"[liveness] UNSAFE {url}: {e}")
            except (httpx.HTTPError, httpx.InvalidURL) as e:
                _update_entry_for_error(entry, error=f"network: {e!s}", today=today)
                stats["network_errors"] += 1
                if verbose:
                    print(f"[liveness] ERROR {url}: {e!s}")

            checks[url] = entry
            stats["checked"] += 1
    finally:
        if owns_client:
            http.close()

    _save_state(state_path, state)
    return stats
