"""Reddit extractor (per-subreddit /new.json).

One HTTP call per sub in `source.subreddits`. Reddit's listing JSON contains a
`data.children` array of post envelopes; we look at each child's `data`
sub-object and keep the ones that:

  - are not self-posts (`is_self == False` — we want outbound links to
    artifacts, not Reddit text threads),
  - don't link back to Reddit's own media domains (`i.redd.it`, etc.),
  - match the configured keyword filter on title (`match.any_of`),
  - classify to a useful kind via `_util.classify_url`.

Cursor: per-sub `created_utc` high-water mark, stored under
`state.cursor["per_sub"][<sub>]`. Each sub advances independently so a quiet
sub doesn't reset a busy one.

`discovered_via` is `f"reddit-{sub.lower()}"` to preserve provenance through
the catalog.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from urllib.parse import urlsplit

import httpx

from .._security import SecurityError, safe_get_bytes, sanitize_text
from .._util import classify_url, matches_any, slugify
from ..agent.types import Candidate, RedditSource, SourceState

_REDDIT_OWN_HOSTS = frozenset(
    {
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
        "i.redd.it",
        "v.redd.it",
        "redd.it",
    }
)


class RedditExtractor:
    type = "reddit"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "ft-autoclaude-scout/0.1.0"},
        )

    def fetch(
        self,
        source: RedditSource,
        state: SourceState,
        run_id: str,
    ) -> Iterator[Candidate]:
        today = date.today().isoformat()
        per_sub_cursor: dict = state.cursor.setdefault("per_sub", {})
        keywords = source.match.any_of

        for sub in source.subreddits:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=100"
            try:
                body = safe_get_bytes(self._client, url)
                payload = json.loads(body)
                children = payload["data"]["children"]
            except (
                SecurityError,
                httpx.HTTPError,
                json.JSONDecodeError,
                KeyError,
                TypeError,
            ) as e:
                state.stats.setdefault("sub_errors", []).append(
                    {"sub": sub, "error": str(e), "at": today}
                )
                continue

            cursor = float(per_sub_cursor.get(sub) or 0.0)
            max_seen = cursor

            for child in children:
                data = child.get("data") or {}

                if data.get("is_self"):
                    continue

                post_url = (data.get("url") or "").strip()
                if not post_url:
                    continue

                host = (urlsplit(post_url).hostname or "").lower()
                if host in _REDDIT_OWN_HOSTS:
                    continue

                created_utc = float(data.get("created_utc") or 0.0)
                if created_utc <= cursor:
                    continue
                if created_utc > max_seen:
                    max_seen = created_utc

                raw_title = data.get("title") or ""
                if not matches_any(raw_title, keywords):
                    continue

                classification = classify_url(post_url)
                if classification is None:
                    continue
                kind, source_type = classification

                if post_url in state.seen_urls:
                    continue
                state.seen_urls[post_url] = today

                title = sanitize_text(raw_title, max_length=300)
                author = sanitize_text(data.get("author") or "", max_length=100)
                permalink = data.get("permalink") or ""

                yield Candidate(
                    name=slugify(title) or slugify(post_url),
                    kind=kind,
                    title=title,
                    source_type=source_type,
                    source_url=post_url,
                    source_authors=[author] if author else [],
                    discovered_via=f"reddit-{sub.lower()}",
                    discovered_on=today,
                    run_id=run_id,
                    raw_title=title,
                    raw_url=f"https://www.reddit.com{permalink}" if permalink else url,
                    score=int(data.get("score") or 0),
                )

            if max_seen != cursor:
                per_sub_cursor[sub] = max_seen
