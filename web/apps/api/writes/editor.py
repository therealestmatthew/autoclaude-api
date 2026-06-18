"""Frontmatter / body edit primitives.

Each function is a single logical write that produces one git commit:
- `edit_frontmatter` replaces the frontmatter; body untouched.
- `edit_body` replaces the body; frontmatter untouched.
- `edit_full` replaces both.

All three honour `expected_version` for optimistic locking. The caller
(router) wraps the call in `begin_audit` so the operation is auditable.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import fs, git, serialize


class VersionMismatch(RuntimeError):
    """Raised when the caller's `expected_version` doesn't match the
    current state on disk. Translates to HTTP 409."""

    def __init__(self, *, current_version: str, expected_version: str):
        self.current_version = current_version
        self.expected_version = expected_version
        super().__init__(
            f"version mismatch: expected {expected_version!r}, "
            f"current {current_version!r}"
        )


class DirtyTree(RuntimeError):
    """Raised when the repo's working tree has uncommitted changes that
    overlap the paths the writer wants to touch. The writer refuses to
    proceed; the operator commits or stashes and retries."""


# Process-wide lock around any write. Serialises edits + triage so two
# in-flight requests can't race on the same path. Cheap (one mutex);
# v1 doesn't need finer granularity.
_WRITE_LOCK = threading.Lock()


@dataclass(frozen=True)
class WriteResult:
    path: str
    commit_sha: str
    new_version: str
    commit_created: bool


def _hash_text(text: str) -> str:
    """Content hash matches what the indexer computes — see
    `web.apps.api.db.sync._hash_record`. For the optimistic-lock check
    we don't need bytewise parity; we need stable identity. Reuse the
    same hash by re-parsing the doc into an AssetRecord-shaped dict."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _refuse_dirty(repo_root: Path, target: Path) -> None:
    """Raise DirtyTree if the working tree already has changes that
    would conflict with the write."""
    target_rel = str(target.resolve().relative_to(repo_root.resolve()))
    for line in git.status_porcelain(repo_root):
        # Porcelain v1: `XY <path>` where XY is the status pair.
        path_part = line[3:].strip()
        if path_part == target_rel or path_part.startswith(target_rel + "/"):
            raise DirtyTree(f"working tree already changed: {path_part}")


def _read_current_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def edit_frontmatter(
    repo_root: Path,
    rel_path: str,
    *,
    frontmatter: dict[str, Any],
    expected_version: str,
    commit_message: str,
) -> WriteResult:
    """Replace the frontmatter of the file at `rel_path` and commit."""
    with _WRITE_LOCK:
        target = fs.safe_path(repo_root, rel_path)
        current_text = _read_current_text(target)
        current_hash = _hash_text(current_text)
        if current_hash != expected_version:
            raise VersionMismatch(
                current_version=current_hash, expected_version=expected_version
            )
        _refuse_dirty(repo_root, target)

        new_text = serialize.replace_frontmatter(current_text, frontmatter)
        fs.atomic_write(target, new_text)
        try:
            sha, created = git.commit(
                repo_root,
                paths=[target],
                message=commit_message,
                must_commit=True,
            )
        except Exception:
            git.checkout_paths(repo_root, [target])
            raise
        return WriteResult(
            path=rel_path,
            commit_sha=sha,
            new_version=_hash_text(new_text),
            commit_created=created,
        )


def edit_body(
    repo_root: Path,
    rel_path: str,
    *,
    body: str,
    expected_version: str,
    commit_message: str,
) -> WriteResult:
    with _WRITE_LOCK:
        target = fs.safe_path(repo_root, rel_path)
        current_text = _read_current_text(target)
        current_hash = _hash_text(current_text)
        if current_hash != expected_version:
            raise VersionMismatch(
                current_version=current_hash, expected_version=expected_version
            )
        _refuse_dirty(repo_root, target)

        new_text = serialize.replace_body(current_text, body)
        fs.atomic_write(target, new_text)
        try:
            sha, created = git.commit(
                repo_root,
                paths=[target],
                message=commit_message,
                must_commit=True,
            )
        except Exception:
            git.checkout_paths(repo_root, [target])
            raise
        return WriteResult(
            path=rel_path,
            commit_sha=sha,
            new_version=_hash_text(new_text),
            commit_created=created,
        )


def edit_full(
    repo_root: Path,
    rel_path: str,
    *,
    frontmatter: dict[str, Any],
    body: str,
    expected_version: str,
    commit_message: str,
) -> WriteResult:
    with _WRITE_LOCK:
        target = fs.safe_path(repo_root, rel_path)
        current_text = _read_current_text(target)
        current_hash = _hash_text(current_text)
        if current_hash != expected_version:
            raise VersionMismatch(
                current_version=current_hash, expected_version=expected_version
            )
        _refuse_dirty(repo_root, target)

        new_text = serialize.render_document(frontmatter, body)
        fs.atomic_write(target, new_text)
        try:
            sha, created = git.commit(
                repo_root,
                paths=[target],
                message=commit_message,
                must_commit=True,
            )
        except Exception:
            git.checkout_paths(repo_root, [target])
            raise
        return WriteResult(
            path=rel_path,
            commit_sha=sha,
            new_version=_hash_text(new_text),
            commit_created=created,
        )


def current_version_for(repo_root: Path, rel_path: str) -> str:
    """Compute the optimistic-lock token for a path from disk content.

    Used by the router to populate the `If-Match` value the UI gets on
    a GET. We hash the raw bytes (same as `_hash_text`) — this is the
    optimistic-lock token; the DB's `Asset.version` is a sync-time
    mirror of the same value and may lag by up to one reconcile cycle.
    """
    target = fs.safe_path(repo_root, rel_path)
    return _hash_text(_read_current_text(target))
