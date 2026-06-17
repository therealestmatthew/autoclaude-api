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
    rels = [
        str(p.resolve().relative_to(repo_root.resolve())) for p in paths
    ]
    if not rels:
        return
    _run(repo_root, ["add", "--", *rels])


def commit(
    repo_root: Path,
    *,
    paths: Iterable[Path],
    message: str,
    author_name: str | None = None,
    author_email: str | None = None,
) -> str:
    """Stage the given paths and commit them. Returns the new SHA.

    Never uses `--no-verify`; hook failures propagate.
    """
    if not author_name or not author_email:
        a_name, a_email = resolve_author(repo_root)
        author_name = author_name or a_name
        author_email = author_email or a_email

    add_paths(repo_root, paths)
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
    return head_sha(repo_root)


def checkout_paths(repo_root: Path, paths: Iterable[Path]) -> None:
    """Roll back unstaged changes on the given paths. Used by the
    rollback path when a commit fails after the file was written."""
    rels = [
        str(p.resolve().relative_to(repo_root.resolve())) for p in paths
    ]
    if not rels:
        return
    _run(repo_root, ["checkout", "--", *rels])
