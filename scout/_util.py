"""Tiny shared helpers used across the runner and extractors.

Pure functions, no I/O. Kept in one module to avoid import cycles and to keep
their tests adjacent. Add a helper here when a second consumer wants it; not
before.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

_NON_SLUG = re.compile(r"[^a-z0-9]+")

# GitHub *repo* URLs: https?://github.com/<owner>/<repo>[/...].
# Owner / repo allow dot, dash, underscore. Owner+repo are captured for
# canonicalization. Trailing characters can be anything (path, query, fragment).
_GITHUB_REPO = re.compile(
    r"^https?://github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)"
)

# Prefixes under github.com that look like a repo but aren't useful artifacts.
_GITHUB_NOT_USEFUL = re.compile(
    r"^https?://github\.com/(?:sponsors|topics|search|orgs|features|"
    r"marketplace|trending|notifications|settings|about|pricing|enterprise|"
    r"login|signup|join|stars|readme|account|codespaces)(?:/|$)"
)


def slugify(text: str, max_length: int = 60) -> str:
    """Produce a kebab-case slug from a free-form title."""
    s = _NON_SLUG.sub("-", text.lower()).strip("-")
    if max_length > 0:
        s = s[:max_length].rstrip("-")
    return s or "unnamed"


def canonical_github_url(url: str) -> str:
    """Reduce a GitHub URL to `https://github.com/<owner>/<repo>` form.

    Used to dedup against the catalog when a source links to a subpath of a repo
    we already track. Non-GitHub URLs are returned with trailing slashes stripped
    but otherwise untouched.
    """
    m = _GITHUB_REPO.match(url)
    if m:
        owner, repo = m.group(1), m.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return f"https://github.com/{owner}/{repo}"
    return url.rstrip("/")


def is_github_repo_url(url: str) -> bool:
    """True iff URL looks like a useful GitHub repo path (owner/repo and not a
    sponsors/topics/etc surface)."""
    if not _GITHUB_REPO.match(url):
        return False
    return not _GITHUB_NOT_USEFUL.match(url)


def classify_url(url: str) -> tuple[str, str] | None:
    """Map a URL to `(kind, source_type)` for catalog purposes.

    - useful GitHub repo URL → `("repo", "github")`
    - any other http(s) URL  → `("article", "article")`
    - non-http URL or useless GitHub path → `None` (skip)

    Callers that want GitHub-only behavior (e.g. the awesome-list extractor)
    filter the result by `kind == "repo"`.
    """
    if _GITHUB_REPO.match(url):
        # GitHub URL — keep only useful repos.
        return ("repo", "github") if is_github_repo_url(url) else None
    if url.startswith(("http://", "https://")):
        return ("article", "article")
    return None


def matches_any(text: str, keywords: list[str]) -> bool:
    """Case-insensitive substring match: True iff text contains any keyword.

    Empty keyword list returns True (no filter = let everything through).
    """
    if not keywords:
        return True
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in keywords)


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse YAML frontmatter from a markdown document.

    Returns the mapping if the doc starts with `---\\n...\\n---`, else `{}`.
    Malformed YAML inside the fences also returns `{}` — callers treat the
    catalog as best-effort and don't crash on a single bad file.
    """
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        loaded = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
