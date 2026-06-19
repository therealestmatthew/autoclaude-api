"""Retrieve catalog context for a queue candidate.

Reads catalog files directly (no HTTP dependency) so the reviewer CLI works
without the API server running. Returns the top-N catalog assets by relevance:
- substring match in title / tags / slug
- shared tag count

This is intentionally simple — vector embeddings replace it in 9.x.
"""

from __future__ import annotations

import re
from pathlib import Path

from .._util import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parents[2]
_CATALOG_DIR = REPO_ROOT / "catalog"


def _split_body(text: str) -> str:
    """Return the markdown body after the closing --- fence."""
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    return parts[2].strip() if len(parts) >= 3 else ""


def _load_catalog_index(catalog_dir: Path = _CATALOG_DIR) -> list[dict]:
    """Load frontmatter for every catalog asset. Cached in-process."""
    items = []
    for p in catalog_dir.glob("*.md"):
        if p.name.startswith("_"):
            continue
        text = p.read_text()
        fm = parse_frontmatter(text)
        if not fm:
            continue
        body = _split_body(text)
        slug = fm.get("slug") or p.stem
        items.append(
            {
                "slug": slug,
                "title": fm.get("title", ""),
                "kind": fm.get("kind"),
                "status": fm.get("status"),
                "tags": fm.get("tags") or [],
                "body_excerpt": body[:200].strip() if body else "",
            }
        )
    return items


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score(candidate_tokens: set[str], candidate_tags: set[str], item: dict) -> float:
    title_tokens = _tokenize(item.get("title", ""))
    slug_tokens = _tokenize(item.get("slug", ""))
    item_tags = {t.lower() for t in (item.get("tags") or [])}

    title_match = len(candidate_tokens & title_tokens) / max(len(title_tokens), 1)
    slug_match = len(candidate_tokens & slug_tokens) / max(len(slug_tokens), 1)
    tag_overlap = len(candidate_tags & item_tags)

    return title_match * 2.0 + slug_match * 1.0 + tag_overlap * 1.5


def get_context(
    title: str,
    tags: list[str],
    top_n: int = 7,
    catalog_dir: Path = _CATALOG_DIR,
) -> list[dict]:
    """Return up to top_n catalog items relevant to the candidate."""
    catalog = _load_catalog_index(catalog_dir)
    candidate_tokens = _tokenize(title)
    candidate_tags = {t.lower() for t in tags}

    scored = [(item, _score(candidate_tokens, candidate_tags, item)) for item in catalog]
    scored.sort(key=lambda x: -x[1])
    return [item for item, score in scored[:top_n] if score > 0.0]
