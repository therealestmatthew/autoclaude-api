"""Soft-overlap detection for dedup pass 3.

Title-token Jaccard + primary-author normalization. Conservative by design —
false positives waste a reviewer minute; false negatives accumulate dupes
forever.
"""

from __future__ import annotations

import re

_STOPWORDS = frozenset(
    {
        "a", "an", "and", "the", "to", "of", "in", "on", "for", "with",
        "by", "is", "as", "or", "be", "at", "that", "this", "it", "from",
        "via", "vs", "use", "using", "how", "what", "why", "your", "you",
    }
)

_TOKEN = re.compile(r"[a-z0-9]+")


def title_tokens(title: str) -> set[str]:
    """Lowercased word-tokens with stopwords removed. Tokens shorter than 2
    chars are also dropped — they're almost always noise (single letters,
    initials)."""
    if not isinstance(title, str):
        return set()
    return {
        t for t in _TOKEN.findall(title.lower())
        if t not in _STOPWORDS and len(t) > 1
    }


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity. 0.0 when both sides are empty."""
    if not a and not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def primary_author(authors: list[str] | None) -> str:
    """Lower-cased first author slug. Empty string if absent. Two items with
    distinct first authors are never grouped — keeps the bucket count high
    and the cross-comparison cost O(N) per bucket instead of O(N²) overall."""
    if not isinstance(authors, list) or not authors:
        return ""
    first = authors[0]
    return first.lower().strip() if isinstance(first, str) else ""
