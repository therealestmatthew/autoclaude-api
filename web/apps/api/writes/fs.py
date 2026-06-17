"""Path validation and atomic write primitives.

Every UI-driven write touches the repo through these helpers. They:
- Refuse paths outside the repo root.
- Refuse symlinks (defense against path-traversal via dangling links).
- Refuse `..` components even after resolution.
- Write via a temp file + `os.replace` so a crash never leaves a
  half-written markdown file.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


class UnsafePath(ValueError):
    """Raised when a candidate path escapes its repo root or trips a
    defensive check."""


def safe_path(repo_root: Path, rel: str) -> Path:
    """Resolve `rel` against `repo_root` and verify it stays inside.

    Rejects:
    - Absolute `rel` (must be repo-relative).
    - Path components that include `..`.
    - Anything that resolves outside `repo_root`.
    - Symlinks anywhere in the resolved chain (a defensive measure;
      the catalog has no legitimate symlinks).
    """
    if not rel:
        raise UnsafePath("empty path")
    candidate = Path(rel)
    if candidate.is_absolute():
        raise UnsafePath(f"absolute path not allowed: {rel}")
    if ".." in candidate.parts:
        raise UnsafePath(f"`..` not allowed in path: {rel}")

    repo_resolved = repo_root.resolve()
    full = (repo_resolved / candidate).resolve()
    try:
        full.relative_to(repo_resolved)
    except ValueError as e:
        raise UnsafePath(f"path escapes repo root: {rel}") from e

    # Walk the existing path components and reject symlinks. We check
    # only existing components — the file we're about to write may not
    # exist yet, and that's fine.
    cur = repo_resolved
    for part in candidate.parts:
        cur = cur / part
        if cur.is_symlink():
            raise UnsafePath(f"symlink in path: {cur.relative_to(repo_resolved)}")
        if not cur.exists():
            break

    return full


def atomic_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Write `content` to `path` via a temp file + rename.

    Crash semantics: either the old file is intact (rename never
    happened) or the new file is intact (rename completed). No
    half-written state is observable.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup; the failure is what we're propagating.
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def safe_delete(path: Path, repo_root: Path) -> None:
    """Delete `path` after verifying it stays inside `repo_root` and
    isn't a symlink. No-op if the file is already gone."""
    resolved_root = repo_root.resolve()
    try:
        path.resolve().relative_to(resolved_root)
    except ValueError as e:
        raise UnsafePath(f"refuse to delete outside repo root: {path}") from e
    if path.is_symlink():
        raise UnsafePath(f"refuse to delete symlink: {path}")
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
