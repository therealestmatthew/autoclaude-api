"""Awesome-list extractor.

Fetches markdown README(s) of curated lists, parses out links, filters to
GitHub repository URLs, dedups against the source's persisted `seen_urls`, and
yields a Candidate per new link.

GitHub-only filtering is intentional for Phase 2 — most signal in
awesome-claude-code et al. is GitHub-hosted, and broadening the filter later
is a one-line change once we know what we're missing.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date

import httpx

from .._util import slugify
from ..agent.types import (
    AwesomeListSource,
    Candidate,
    SourceState,
)

# Matches a markdown inline link `[text](url)`. The URL group disallows
# whitespace and unbalanced parens to avoid swallowing trailing prose.
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")

# Only emit candidates for what looks like a GitHub repo (owner/repo, possibly
# with trailing path). The owner/repo names disallow further slashes here so we
# match the *repo* portion cleanly; extra path is preserved on the URL itself.
_GITHUB_REPO_URL = re.compile(
    r"^https?://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+(?:[/?#]|$)"
)

# URLs that look like a repo but aren't useful asset targets.
_NOT_USEFUL = re.compile(
    r"https?://github\.com/(?:sponsors|topics|search|orgs|features|"
    r"marketplace|trending|notifications|settings)(?:/|$)"
)


class AwesomeListExtractor:
    """Extractor for source `type: awesome-list`."""

    type = "awesome-list"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "autoclaude-scout/0.1.0"},
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
                resp = self._client.get(lst.url)
                resp.raise_for_status()
                content = resp.text
            except Exception as e:
                # External boundary: record and move on. Don't let one bad list
                # poison the run.
                state.stats.setdefault("list_errors", []).append(
                    {"list": lst.name, "url": lst.url, "error": str(e), "at": today}
                )
                continue

            for match in _LINK.finditer(content):
                title = match.group(1).strip()
                url = match.group(2).strip().rstrip(".,")  # strip stray punctuation
                if not _is_useful_url(url):
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


def _is_useful_url(url: str) -> bool:
    if not _GITHUB_REPO_URL.match(url):
        return False
    return not _NOT_USEFUL.match(url)
