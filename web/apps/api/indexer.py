"""Repo walker that produces a typed record per markdown document.

This is the v1 read layer for the web app. Pure function over a repo root:
walk all tracked-shape markdown, parse frontmatter (sharing the same parser
that scout uses), classify by path into a bucket (catalog / queue / engagement
/ ...), and emit `AssetRecord`s.

The output is what every FastAPI router reads. No I/O happens inside the
routers — they hand off to `CachedIndex` which wraps this module.

Determinism: walking a fixed filesystem snapshot produces a fixed record list,
sorted by path. Tests rely on this.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from scout._util import parse_frontmatter

Bucket = Literal[
    "catalog",
    "queue",
    "engagement",
    "convention",
    "plan",
    "session_prompt",
    "runbook",
    "readme",
    "claude",
    "consulting",
    "brand",
    "timeline",
    "other",
]

ALL_BUCKETS: tuple[Bucket, ...] = (
    "catalog",
    "queue",
    "engagement",
    "convention",
    "plan",
    "session_prompt",
    "runbook",
    "readme",
    "claude",
    "consulting",
    "brand",
    "timeline",
    "other",
)

# Directories whose entire contents we never index (build artifacts, deps).
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".next",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
        ".eggs",
    }
)


@dataclass(frozen=True)
class AssetRecord:
    path: str                          # repo-relative POSIX path
    bucket: Bucket
    slug: str                          # name field, or filename stem fallback
    kind: str | None
    title: str | None
    status: str | None
    quality: int | None
    tags: tuple[str, ...]
    delivery_functions: tuple[str, ...]  # from `delivery_function:` frontmatter field
    source: dict | None
    discovered: dict | None
    relations: dict | None
    created_at: str | None
    updated_at: str | None
    body: str
    issues: tuple[str, ...]
    mtime: float
    # 8.3: SHA-256 of the raw file bytes. Used as the optimistic-lock
    # token (`version`) by write-back. Different from the sync engine's
    # `content_hash` (which is a JSON-normalised hash of the record's
    # wire-shape fields and ignores byte-for-byte differences like
    # whitespace). For writes, we want byte-for-byte sensitivity so the
    # operator sees a 409 if anything at all changed under them.
    raw_hash: str = ""


@dataclass(frozen=True)
class IndexStats:
    total: int
    by_bucket: dict[Bucket, int]
    by_kind: dict[str, int]
    by_status: dict[str, int]
    with_issues: int


@dataclass
class IndexSnapshot:
    """Result of a single full scan. Frozen-ish — callers don't mutate."""

    records: list[AssetRecord] = field(default_factory=list)
    scan_mtime_ceiling: float = 0.0    # max mtime observed during the scan
    repo_root: str = ""

    def by_slug(self) -> dict[str, AssetRecord]:
        out: dict[str, AssetRecord] = {}
        for r in self.records:
            # Preserve first-seen on duplicate slugs across buckets; record the
            # collision as an issue on the later one.
            if r.slug in out:
                collided = replace(
                    r,
                    issues=(*r.issues, f"slug-collision:{out[r.slug].path}"),
                )
                out[f"{r.bucket}:{r.slug}"] = collided
            else:
                out[r.slug] = r
        return out

    def by_bucket(self) -> dict[Bucket, list[AssetRecord]]:
        groups: dict[Bucket, list[AssetRecord]] = defaultdict(list)
        for r in self.records:
            groups[r.bucket].append(r)
        return dict(groups)

    def stats(self) -> IndexStats:
        by_bucket: dict[Bucket, int] = defaultdict(int)
        by_kind: dict[str, int] = defaultdict(int)
        by_status: dict[str, int] = defaultdict(int)
        with_issues = 0
        for r in self.records:
            by_bucket[r.bucket] += 1
            if r.kind:
                by_kind[r.kind] += 1
            if r.status:
                by_status[r.status] += 1
            if r.issues:
                with_issues += 1
        return IndexStats(
            total=len(self.records),
            by_bucket=dict(by_bucket),
            by_kind=dict(by_kind),
            by_status=dict(by_status),
            with_issues=with_issues,
        )


def classify_bucket(path: Path, repo_root: Path) -> Bucket:
    """Decide which bucket a markdown file belongs to based on its path."""
    rel = path.relative_to(repo_root).as_posix()
    parts = rel.split("/")
    name = parts[-1]

    # READMEs almost everywhere get their own bucket — except where the README
    # is the canonical document for an engagement.
    is_readme = name.lower() == "readme.md"

    if parts[0] == "brands":
        # _template subtree is a scaffold, not a real brand.
        if len(parts) >= 2 and parts[1] == "_template":
            return "readme" if is_readme else "other"
        if is_readme:
            return "readme"
        return "brand"

    if parts[0] == "timelines":
        # _template.md is a scaffold, not a real timeline.
        if name == "_template.md":
            return "other"
        if is_readme:
            return "readme"
        return "timeline"

    if parts[0] == "catalog":
        # Skip the schema spec and the example/template subtrees.
        if len(parts) >= 2 and parts[1] in {"_schema", "_examples"}:
            return "readme" if is_readme else "other"
        if is_readme:
            return "readme"
        return "catalog"

    if parts[:2] == ["scout", "queue"]:
        if is_readme or name == "_template.md":
            return "readme" if is_readme else "other"
        return "queue"

    if parts[:2] == ["consulting", "engagements"]:
        # `_template` subtree is itself a template, not a real engagement.
        if len(parts) >= 3 and parts[2] == "_template":
            return "readme" if is_readme else "other"
        # The engagement root README *is* the canonical record.
        if len(parts) == 4 and is_readme:
            return "engagement"
        return "readme" if is_readme else "other"

    if parts[0] == "consulting":
        return "readme" if is_readme else "consulting"

    if parts[0] == "conventions":
        return "readme" if is_readme else "convention"

    if parts[:2] == ["docs", "plans"]:
        if "session_prompts" in parts:
            return "session_prompt" if not is_readme else "readme"
        return "readme" if is_readme else "plan"

    if parts[:2] == ["docs", "runbooks"] or parts[:2] == ["command-center", "runbooks"]:
        return "readme" if is_readme else "runbook"

    if parts[0] == "claude":
        return "readme" if is_readme else "claude"

    if is_readme:
        return "readme"

    return "other"


_SLUG_FALLBACK = re.compile(r"[^a-z0-9]+")


def _slug_from_filename(path: Path) -> str:
    stem = path.stem.lower()
    return _SLUG_FALLBACK.sub("-", stem).strip("-") or "unnamed"


def _split_body(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].lstrip("\n")


def _coerce_tags(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(v) for v in value)
    if isinstance(value, str) and value:
        return (value,)
    return ()


def _coerce_quality(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _coerce_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _coerce_date(value: object) -> str | None:
    """Frontmatter dates can come back as `datetime.date` from PyYAML. Render
    everything as ISO strings on the wire."""
    if value is None:
        return None
    # `datetime.date` — duck-typed to avoid importing.
    if hasattr(value, "isoformat") and callable(value.isoformat):  # type: ignore[truthy-function]
        try:
            return value.isoformat()  # type: ignore[call-arg]
        except Exception:
            pass
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _record_from_path(path: Path, repo_root: Path) -> AssetRecord:
    rel = path.relative_to(repo_root).as_posix()
    bucket = classify_bucket(path, repo_root)
    try:
        text = path.read_text(encoding="utf-8")
        read_ok = True
    except (OSError, UnicodeDecodeError) as e:
        text = ""
        read_ok = False
        read_error = f"read-error:{e.__class__.__name__}"

    issues: list[str] = []
    if not read_ok:
        issues.append(read_error)

    fm = parse_frontmatter(text) if read_ok else {}
    if read_ok and not fm and text.startswith("---"):
        issues.append("malformed-frontmatter")
    elif read_ok and not text.startswith("---"):
        issues.append("missing-frontmatter")

    slug_field = _coerce_str(fm.get("name"))
    slug = slug_field or _slug_from_filename(path)
    if slug_field is None and bucket in {"catalog", "queue", "engagement"}:
        issues.append("missing-name")

    title = _coerce_str(fm.get("title"))
    if title is None and bucket in {"catalog", "queue", "engagement", "plan"}:
        issues.append("missing-title")

    status = _coerce_str(fm.get("status"))
    kind = _coerce_str(fm.get("kind"))

    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0

    raw_hash = (
        hashlib.sha256(text.encode("utf-8")).hexdigest() if read_ok else ""
    )

    return AssetRecord(
        path=rel,
        bucket=bucket,
        slug=slug,
        kind=kind,
        title=title,
        status=status,
        quality=_coerce_quality(fm.get("quality")),
        tags=_coerce_tags(fm.get("tags")),
        delivery_functions=_coerce_tags(fm.get("delivery_function")),
        source=fm.get("source") if isinstance(fm.get("source"), dict) else None,
        discovered=fm.get("discovered") if isinstance(fm.get("discovered"), dict) else None,
        relations=fm.get("relations") if isinstance(fm.get("relations"), dict) else None,
        created_at=_coerce_date(fm.get("created_at")),
        updated_at=_coerce_date(fm.get("updated_at")),
        body=_split_body(text),
        issues=tuple(issues),
        mtime=mtime,
        raw_hash=raw_hash,
    )


def _walk_markdown(repo_root: Path) -> list[Path]:
    """Walk the tree, skipping noise dirs, and return all .md paths sorted."""
    found: list[Path] = []
    for current in sorted({repo_root}):
        for entry in _iter_tree(current):
            if entry.suffix.lower() in {".md", ".markdown"}:
                found.append(entry)
    found.sort(key=lambda p: p.as_posix())
    return found


def _iter_tree(root: Path):
    """Manual walker so we can prune _SKIP_DIRS without a callback dance."""
    stack: list[Path] = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name in _SKIP_DIRS:
                    continue
                stack.append(entry)
            elif entry.is_file():
                yield entry


class Indexer:
    """One-shot repo walker. Hold an instance per request lifetime; the cache
    layer (see `cache.py`) is what you actually use from FastAPI."""

    def __init__(self, repo_root: Path) -> None:
        if not repo_root.is_dir():
            raise NotADirectoryError(f"repo_root not a directory: {repo_root}")
        self.repo_root = repo_root.resolve()

    def scan(self) -> IndexSnapshot:
        records: list[AssetRecord] = []
        max_mtime = 0.0
        for path in _walk_markdown(self.repo_root):
            rec = _record_from_path(path, self.repo_root)
            records.append(rec)
            if rec.mtime > max_mtime:
                max_mtime = rec.mtime
        return IndexSnapshot(
            records=records,
            scan_mtime_ceiling=max_mtime,
            repo_root=self.repo_root.as_posix(),
        )
