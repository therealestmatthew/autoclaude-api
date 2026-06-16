"""Identity keys for dedup passes 1 and 2.

Pass 1 (identity) groups by exact URL or fingerprint. Pass 2 (URL canonical)
groups by canonical_github_url, which collapses subpath links into the
underlying repo.
"""

from __future__ import annotations

import hashlib

from .._util import canonical_github_url


def url_key(url: str) -> str:
    """Exact-URL identity key. Trailing slash stripped for stability."""
    return url.rstrip("/") if isinstance(url, str) and url else ""


def canonical_url_key(url: str) -> str:
    """Canonical-URL identity key. Subpaths of a github repo collapse to the
    repo's `https://github.com/<owner>/<repo>` form. Non-github URLs round-
    trip through `rstrip('/')` (matches `canonical_github_url`)."""
    if not isinstance(url, str) or not url:
        return ""
    return canonical_github_url(url)


def fingerprint_key(fp: str | None) -> str:
    """Fingerprint identity key. Empty string when absent or malformed."""
    if not isinstance(fp, str):
        return ""
    return fp.strip()


def slug_set_hash(slugs: list[str], length: int = 8) -> str:
    """Stable hash of a sorted slug list — used to form `mergeset_id`. The
    same membership produces the same id across runs, which is required for
    idempotent pass 3 behavior."""
    payload = "|".join(sorted(slugs)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]
