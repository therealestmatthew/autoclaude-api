"""Awesome-list extractor.

Fetches markdown README(s) of curated lists, parses out `[text](url)` links,
keeps only useful GitHub repo URLs, dedups against the source's persisted
`seen_urls`, and yields a Candidate per new link.

GitHub-only filtering is intentional — most signal in awesome-claude-code et al.
is GitHub-hosted, and links to project websites are usually less valuable to
catalog than the underlying repos.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date

import httpx

from .._security import SecurityError, safe_get_bytes, sanitize_text
from .._util import classify_url, slugify
from ..agent.types import (
    AwesomeListSource,
    Candidate,
    SourceState,
)

# Markdown inline link `[text](url)`. URL group disallows whitespace and `)` so
# we don't swallow trailing prose like `... (alt text)`.
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


class AwesomeListExtractor:
    """Extractor for source `type: awesome-list`."""

    type = "awesome-list"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "ft-autoclaude-scout/0.1.0"},
        )

    def fetch(
        self,
        source: AwesomeListSource,
        state: SourceState,
        run_id: str,
    ) -> Iterator[Candidate]:
        today = date.today().isoformat()
        for lst in source.lists:
            try:
                content = safe_get_bytes(self._client, lst.url).decode(
                    "utf-8", errors="replace"
                )
            except (SecurityError, httpx.HTTPError) as e:
                state.stats.setdefault("list_errors", []).append(
                    {"list": lst.name, "url": lst.url, "error": str(e), "at": today}
                )
                continue

            for match in _LINK.finditer(content):
                title = sanitize_text(match.group(1), max_length=300)
                url = match.group(2).strip().rstrip(".,")
                if not title:
                    continue
                classification = classify_url(url)
                # Awesome-list policy: GitHub repos only.
                if classification is None or classification[0] != "repo":
                    continue
                if url in state.seen_urls:
                    continue
                state.seen_urls[url] = today
                yield Candidate(
                    name=slugify(title) or slugify(url),
                    kind="repo",
                    title=title,
                    source_type="github",
                    source_url=url,
                    discovered_via=lst.name,
                    discovered_on=today,
                    run_id=run_id,
                    raw_title=title,
                    raw_url=lst.url,
                )
