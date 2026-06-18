"""Unit tests for the git subprocess wrapper.

Pin the contract of `commit()` post-8.3 hardening: it returns
`(sha, commit_created)`, and `must_commit` controls whether a no-op
raises `NothingToCommit` or returns `(HEAD, False)`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from web.apps.api.writes.git import NothingToCommit, commit, head_sha


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        },
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo with one initial commit so HEAD resolves."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "README.md").write_text("seed\n")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_commit_creates_new_sha_when_something_staged(repo: Path) -> None:
    target = repo / "catalog" / "alpha.md"
    target.parent.mkdir(parents=True)
    target.write_text("hello\n")
    before = head_sha(repo)
    sha, created = commit(repo, paths=[target], message="add alpha")
    assert created is True
    assert sha != before
    assert head_sha(repo) == sha


def test_commit_raises_nothing_to_commit_when_must(repo: Path) -> None:
    """`must_commit=True` (default) + nothing staged → NothingToCommit.

    Simulates the bug class the 8.3 dogfood exposed: a writer expected
    a commit and didn't get one. Failing loudly here beats silently
    recording a stale SHA.

    Setup: a gitignored queue path that was created then deleted on
    disk before commit() ran. `git add` sees nothing to match, the
    add tolerates it, but the writer still demanded a commit.
    """
    (repo / ".gitignore").write_text("queue/*\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore queue")

    qdir = repo / "queue"
    qdir.mkdir()
    ghost = qdir / "candidate.md"
    ghost.write_text("x")
    ghost.unlink()  # gone before commit() runs.

    with pytest.raises(NothingToCommit):
        commit(repo, paths=[ghost], message="should fail")


def test_commit_returns_false_when_optional(repo: Path) -> None:
    """`must_commit=False` + nothing staged → (HEAD, False).

    The `triage_discard` of a gitignored queue file: the queue path
    was already untracked, deleting it produces nothing to commit, and
    that's success, not failure.
    """
    (repo / ".gitignore").write_text("queue/*\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore queue")
    before = head_sha(repo)

    # Create + delete a gitignored file: nothing for git to see.
    qdir = repo / "queue"
    qdir.mkdir()
    qfile = qdir / "candidate.md"
    qfile.write_text("x")
    qfile.unlink()

    sha, created = commit(
        repo, paths=[qfile], message="discard", must_commit=False
    )
    assert created is False
    assert sha == before
    assert head_sha(repo) == before
