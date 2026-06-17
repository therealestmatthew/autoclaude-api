"""Unit tests for the safe-path + atomic-write primitives."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from web.apps.api.writes.fs import UnsafePath, atomic_write, safe_delete, safe_path


def test_safe_path_resolves_inside_root(tmp_path: Path) -> None:
    resolved = safe_path(tmp_path, "catalog/alpha.md")
    assert resolved == (tmp_path / "catalog" / "alpha.md").resolve()


def test_safe_path_rejects_absolute(tmp_path: Path) -> None:
    with pytest.raises(UnsafePath):
        safe_path(tmp_path, "/etc/passwd")


def test_safe_path_rejects_double_dot(tmp_path: Path) -> None:
    with pytest.raises(UnsafePath):
        safe_path(tmp_path, "catalog/../../escape.md")


def test_safe_path_rejects_symlink(tmp_path: Path) -> None:
    (tmp_path / "catalog").mkdir()
    real_target = tmp_path / "elsewhere"
    real_target.mkdir()
    os.symlink(real_target, tmp_path / "catalog" / "linked")
    with pytest.raises(UnsafePath):
        safe_path(tmp_path, "catalog/linked/asset.md")


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "file.md"
    atomic_write(target, "hello\n")
    assert target.read_text() == "hello\n"


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "file.md"
    target.write_text("old")
    atomic_write(target, "new")
    assert target.read_text() == "new"


def test_atomic_write_leaves_no_temp_files(tmp_path: Path) -> None:
    target = tmp_path / "file.md"
    atomic_write(target, "content")
    siblings = list(tmp_path.iterdir())
    assert siblings == [target]


def test_safe_delete_inside_root(tmp_path: Path) -> None:
    target = tmp_path / "file.md"
    target.write_text("x")
    safe_delete(target, tmp_path)
    assert not target.exists()


def test_safe_delete_missing_is_noop(tmp_path: Path) -> None:
    safe_delete(tmp_path / "missing.md", tmp_path)  # does not raise


def test_safe_delete_rejects_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real.md"
    real.write_text("x")
    link = tmp_path / "link.md"
    os.symlink(real, link)
    with pytest.raises(UnsafePath):
        safe_delete(link, tmp_path)
