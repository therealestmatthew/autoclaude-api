"""HackerNews extractor (Algolia `search_by_date` API).

One HTTP call per term in `match.any_of`. Results are deduped within the run
by Algolia's `objectID`, then yielded as Candidates after passing the
`min_points` floor.

Cursor: the highest `created_at_i` seen so far. Subsequent runs query with
`numericFilters=created_at_i>{cursor}` so we never re-fetch old material.

The artifact URL in a hit is the *linked* URL (a blog, a GitHub repo, etc.) —
that becomes `source.url`. The HN item page becomes `scout.raw_url` so the
reviewer has the discussion context one click away.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date

import httpx

from .._security import SecurityError, safe_get_bytes, sanitize_text
from .._util import classify_url, slugify
from ..agent.types import Candidate, HackerNewsSource, SourceState


class HackerNewsExtractor:
    type = "hackernews"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "autoclaude-scout/0.1.0"},
        )

    def fetch(
        self,
        source: HackerNewsSource,
        state: SourceState,
        run_id: str,
    ) -> Iterator[Candidate]:
        today = date.today().isoformat()
        cursor = int(state.cursor.get("last_seen_created_at_i") or 0)
        max_seen = cursor
        min_points = source.match.min_points or 0
        seen_in_run: set[str] = set()

        for term in source.match.any_of:
            params: dict[str, str] = {
                "query": term,
                "tags": "story",
                "hitsPerPage": "100",
            }
            if cursor:
                params["numericFilters"] = f"created_at_i>{cursor}"

            try:
                body = safe_get_bytes(self._client, source.endpoint, params=params)
                hits = json.loads(body).get("hits", [])
            except (SecurityError, httpx.HTTPError, json.JSONDecodeError) as e:
                state.stats.setdefault("term_errors", []).append(
                    {"term": term, "error": str(e), "at": today}
                )
                continue

            for hit in hits:
                object_id = str(hit.get("objectID") or "")
                if not object_id or object_id in seen_in_run:
                    continue
                seen_in_run.add(object_id)

                url = (hit.get("url") or "").strip()
                if not url:                            # Ask HN / poll posts
                    continue

                points = int(hit.get("points") or 0)
                if points < min_points:
                    continue

                created_at_i = int(hit.get("created_at_i") or 0)
                if created_at_i > max_seen:
                    max_seen = created_at_i

                classification = classify_url(url)
                if classification is None:             # mailto, useless github, etc.
                    continue
                kind, source_type = classification

                if url in state.seen_urls:
                    continue
                state.seen_urls[url] = today

                title = sanitize_text(hit.get("title") or "untitled", max_length=300)
                author = sanitize_text(hit.get("author") or "", max_length=100)

                yield Candidate(
                    name=slugify(title) or slugify(url),
                    kind=kind,
                    title=title,
                    source_type=source_type,
                    source_url=url,
                    source_authors=[author] if author else [],
                    discovered_via="hackernews",
                    discovered_on=today,
                    run_id=run_id,
                    raw_title=title,
                    raw_url=f"https://news.ycombinator.com/item?id={object_id}",
                    score=points,
                )

        # Persist the high-water mark so the next run advances the cursor.
        if max_seen != cursor:
            state.cursor["last_seen_created_at_i"] = max_seen
