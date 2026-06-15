"""Tiny shared helpers: slug generation, URL canonicalization, frontmatter parsing.

Three pure functions used across the runner and extractors. Kept here to avoid
import cycles and to keep their tests in one place.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

_NON_SLUG = re.compile(r"[^a-z0-9]+")

_GITHUB_REPO = re.compile(
    r"^https?://github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)"
)


def slugify(text: str, max_length: int = 60) -> str:
    """Produce a kebab-case slug from a free-form title.

    Lowercases, collapses runs of non-alphanumeric chars to single dashes,
    trims dashes, and caps length. Returns 'unnamed' for an empty result.
    """
    s = _NON_SLUG.sub("-", text.lower()).strip("-")
    if max_length > 0:
        s = s[:max_length].rstrip("-")
    return s or "unnamed"


def canonical_github_url(url: str) -> str:
    """Reduce a GitHub URL to its canonical `https://github.com/<owner>/<repo>` form.

    Used to dedup against the catalog when an awesome-list links to a subpath
    (e.g. /tree/main/skills/foo) of a repo we already track.

    Non-GitHub URLs are returned with trailing slashes stripped but otherwise
    untouched.
    """
    m = _GITHUB_REPO.match(url)
    if m:
        owner, repo = m.group(1), m.group(2)
        # Strip a trailing .git if present.
        if repo.endswith(".git"):
            repo = repo[:-4]
        return f"https://github.com/{owner}/{repo}"
    return url.rstrip("/")


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse YAML frontmatter from a markdown document.

    Returns the parsed mapping if the document starts with `---\\n...\\n---`,
    otherwise an empty dict. Malformed YAML inside the fences also returns {} —
    callers are expected to treat the catalog as best-effort and not crash on
    one bad file.
    """
    if not text.startswith("---"):
        return {}
    # Split into [pre, frontmatter, body]; only the middle part matters.
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        loaded = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
