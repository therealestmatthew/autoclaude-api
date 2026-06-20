"""Lobsters extractor (per-tag RSS 2.0 feeds).

Parses the feeds enumerated in the source config, filters titles by
`match.any_of`, and yields one Candidate per matching item.

The `<link>` element is the artifact URL (`source.url`). The `<comments>`
element is the Lobsters discussion URL (`scout.raw_url`).

Cursor: the highest pubDate seen so far (as a UNIX timestamp). On subsequent
runs we skip items with pubDate <= cursor.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from email.utils import parsedate_to_datetime

import httpx
from defusedxml import ElementTree as ET

from .._security import SecurityError, safe_get_bytes, sanitize_text
from .._util import classify_url, matches_any, slugify
from ..agent.types import Candidate, LobstersSource, SourceState


class LobstersExtractor:
    type = "lobsters"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "ft-autoclaude-scout/0.1.0"},
        )

    def fetch(
        self,
        source: LobstersSource,
        state: SourceState,
        run_id: str,
    ) -> Iterator[Candidate]:
        today = date.today().isoformat()
        cursor_ts = float(state.cursor.get("last_seen_pub_ts") or 0.0)
        max_seen_ts = cursor_ts
        keywords = source.match.any_of

        for feed_url in source.feeds:
            try:
                body = safe_get_bytes(self._client, feed_url)
                root = ET.fromstring(body)
            except (SecurityError, httpx.HTTPError, ET.ParseError) as e:
                state.stats.setdefault("feed_errors", []).append(
                    {"feed": feed_url, "error": str(e), "at": today}
                )
                continue

            for item in root.findall("./channel/item"):
                title = sanitize_text(item.findtext("title"), max_length=300)
                link = (item.findtext("link") or "").strip()
                comments = (item.findtext("comments") or "").strip()
                pub_date_str = (item.findtext("pubDate") or "").strip()

                if not link or not title:
                    continue
                if not matches_any(title, keywords):
                    continue

                pub_ts = _parse_pub_ts(pub_date_str)
                if pub_ts is not None and pub_ts <= cursor_ts:
                    continue
                if pub_ts is not None and pub_ts > max_seen_ts:
                    max_seen_ts = pub_ts

                classification = classify_url(link)
                if classification is None:
                    continue
                kind, source_type = classification

                if link in state.seen_urls:
                    continue
                state.seen_urls[link] = today

                yield Candidate(
                    name=slugify(title) or slugify(link),
                    kind=kind,
                    title=title,
                    source_type=source_type,
                    source_url=link,
                    discovered_via="lobsters",
                    discovered_on=today,
                    run_id=run_id,
                    raw_title=title,
                    raw_url=comments or feed_url,
                )

        if max_seen_ts != cursor_ts:
            state.cursor["last_seen_pub_ts"] = max_seen_ts


def _parse_pub_ts(pub_date_str: str) -> float | None:
    """Parse an RFC 2822 RSS pubDate into a UNIX timestamp, or None on failure."""
    if not pub_date_str:
        return None
    try:
        return parsedate_to_datetime(pub_date_str).timestamp()
    except (TypeError, ValueError):
        return None
