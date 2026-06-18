"""Subprocess wrapper around `git`.

Single source of truth for every git operation the write-back layer
performs. Never uses `shell=True`. Never bypasses hooks (no
`--no-verify`). Never amends. Each commit is one logical change.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from pathlib import Path


class GitError(RuntimeError):
    """Wraps a non-zero exit from git with stdout/stderr captured."""

    def __init__(self, cmd: list[str], returncode: int, stdout: str, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            f"git {' '.join(cmd[1:])} failed ({returncode}):\n"
            f"stdout: {stdout.strip()}\nstderr: {stderr.strip()}"
        )


class NothingToCommit(RuntimeError):
    """Raised when `commit()` was called with `must_commit=True` but the
    add step left nothing staged. Distinguishes a real failure (the writer
    expected a commit and didn't get one) from an intentional no-op such
    as `triage_discard` of a gitignored queue file."""


def _run(repo_root: Path, args: list[str], *, env: dict[str, str] | None = None) -> str:
    cmd = ["git", *args]
    completed = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        check=False,
    )
    if completed.returncode != 0:
        raise GitError(cmd, completed.returncode, completed.stdout, completed.stderr)
    return completed.stdout


def status_porcelain(repo_root: Path) -> list[str]:
    """Return parsed `git status --porcelain` lines."""
    out = _run(repo_root, ["status", "--porcelain"])
    return [line for line in out.splitlines() if line.strip()]


def is_tree_clean(repo_root: Path) -> bool:
    return not status_porcelain(repo_root)


def head_sha(repo_root: Path) -> str:
    return _run(repo_root, ["rev-parse", "HEAD"]).strip()


def resolve_author(repo_root: Path) -> tuple[str, str]:
    """Pick the git author identity for write-back commits.

    Priority:
    1. `AUTOCLAUDE_GIT_AUTHOR_NAME` / `_EMAIL` env vars (operator
       override).
    2. `git config user.name` / `user.email` (matches operator's
       existing identity).

    Refuses to fall through to a synthetic default — an unidentified
    commit is a footgun.
    """
    name = os.environ.get("AUTOCLAUDE_GIT_AUTHOR_NAME", "").strip()
    email = os.environ.get("AUTOCLAUDE_GIT_AUTHOR_EMAIL", "").strip()
    if not name:
        try:
            name = _run(repo_root, ["config", "user.name"]).strip()
        except GitError as e:
            raise GitError(
                cmd=e.cmd,
                returncode=e.returncode,
                stdout=e.stdout,
                stderr=(
                    "no git author name configured; "
                    "set AUTOCLAUDE_GIT_AUTHOR_NAME or git config user.name"
                ),
            ) from e
    if not email:
        try:
            email = _run(repo_root, ["config", "user.email"]).strip()
        except GitError as e:
            raise GitError(
                cmd=e.cmd,
                returncode=e.returncode,
                stdout=e.stdout,
                stderr=(
                    "no git author email configured; "
                    "set AUTOCLAUDE_GIT_AUTHOR_EMAIL or git config user.email"
                ),
            ) from e
    return name, email


def add_paths(repo_root: Path, paths: Iterable[Path]) -> None:
    """Stage the given paths. Uses `git add -A -- <path>` per-path so
    deletions are picked up alongside modifications and additions.

    Per-path, not bulk: `git add -A -- A B` is all-or-nothing on the
    command line — if A doesn't match (e.g. it's gitignored or was
    deleted before this call), git errors out and B is never staged.
    Looping per-path with a try/except lets each path's outcome stand
    on its own.

    Tolerates "pathspec did not match" errors: queue files are
    gitignored in the main repo, so a triage that deletes a queue file
    will have nothing for git to stage on the queue side. That's not a
    failure — the catalog-side change (if any) is what we commit. If
    neither side has anything to stage, the caller's `commit()` becomes
    a no-op.
    """
    rels = [
        str(p.resolve().relative_to(repo_root.resolve())) for p in paths
    ]
    for rel in rels:
        try:
            _run(repo_root, ["add", "-A", "--", rel])
        except GitError as e:
            if "did not match any files" in e.stderr:
                continue
            raise


def is_anything_staged(repo_root: Path) -> bool:
    """True if `git diff --cached` has any changes."""
    completed = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    # exit 0: no diff, 1: diff present.
    return completed.returncode != 0


def commit(
    repo_root: Path,
    *,
    paths: Iterable[Path],
    message: str,
    must_commit: bool = True,
    author_name: str | None = None,
    author_email: str | None = None,
) -> tuple[str, bool]:
    """Stage the given paths and commit them.

    Returns `(sha, commit_created)`:
    - `commit_created=True` — a new commit was made; `sha` is the new HEAD.
    - `commit_created=False` — nothing was staged (every path was either
      gitignored or untracked-and-deleted). `sha` is the current HEAD.

    If `must_commit=True` (the default) and nothing was staged,
    `NothingToCommit` is raised. The caller promised a commit and didn't
    get one — that's a bug or a real conflict, not a no-op.

    If `must_commit=False` and nothing was staged, returns
    `(HEAD, False)`. This is the `triage_discard` path: the queue file
    is typically gitignored, so deleting it produces no commit. The
    caller's intent was always "remove from the queue"; no commit was
    ever promised.

    Never uses `--no-verify`; hook failures propagate.
    """
    if not author_name or not author_email:
        a_name, a_email = resolve_author(repo_root)
        author_name = author_name or a_name
        author_email = author_email or a_email

    add_paths(repo_root, paths)
    if not is_anything_staged(repo_root):
        if must_commit:
            raise NothingToCommit(
                "commit() called with must_commit=True but no paths "
                "ended up staged. The writer expected a commit; none "
                "was produced (gitignored or untracked-deleted paths?)."
            )
        return head_sha(repo_root), False

    _run(
        repo_root,
        [
            "-c",
            f"user.name={author_name}",
            "-c",
            f"user.email={author_email}",
            "commit",
            "-m",
            message,
        ],
    )
    return head_sha(repo_root), True


def checkout_paths(repo_root: Path, paths: Iterable[Path]) -> None:
    """Roll back unstaged changes on the given paths. Used by the
    rollback path when a commit fails after the file was written."""
    rels = [
        str(p.resolve().relative_to(repo_root.resolve())) for p in paths
    ]
    if not rels:
        return
    _run(repo_root, ["checkout", "--", *rels])
