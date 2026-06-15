"""Tests for the host-side allowlist + symlink-escape rejection."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from scout.extractors.repo import (
    SymlinkEscape,
    _extract_tar_safely,
    _is_allowed_relpath,
)


def _pack(entries: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, data in entries:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _pack_with_symlink(symlink_name: str, target: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        info = tarfile.TarInfo(name=symlink_name)
        info.type = tarfile.SYMTYPE
        info.linkname = target
        tf.addfile(info)
    return buf.getvalue()


class TestAllowlist:
    @pytest.mark.parametrize("rel", [
        ".claude/agents/foo.md",
        ".claude/skills/x/SKILL.md",
        ".claude/plugins/y/plugin.json",
        ".claude/mcp.json",
        "agents/bar.md",
        "skills/runner/SKILL.md",
        "prompts/triage.md",
        "mcp.json",
        "README.md",
        "README",
        "LICENSE",
        "LICENSE-MIT",
        "CHANGELOG.md",
        ".scout-manifest.json",
    ])
    def test_allows(self, rel: str):
        assert _is_allowed_relpath(rel)

    @pytest.mark.parametrize("rel", [
        "setup.py",
        "scripts/install.sh",
        "tests/test_foo.py",
        "src/main.py",
        "docs/index.rst",
        "config.yaml",                # top-level non-md, non-allowlisted
        "node_modules/x/package.json",
    ])
    def test_denies(self, rel: str):
        assert not _is_allowed_relpath(rel)


class TestExtractTarSafely:
    def test_skips_files_outside_allowlist(self, tmp_path: Path):
        tar = _pack([
            (".claude/agents/foo.md", b"# foo"),
            ("src/secret.py", b"print('boom')"),
        ])
        extracted, _ = _extract_tar_safely(tar, tmp_path)
        assert ".claude/agents/foo.md" in extracted
        assert "src/secret.py" not in extracted
        assert not (tmp_path / "src" / "secret.py").exists()

    def test_rejects_symlink_entry(self, tmp_path: Path):
        tar = _pack_with_symlink("evil", "/etc/passwd")
        with pytest.raises(SymlinkEscape):
            _extract_tar_safely(tar, tmp_path)

    def test_returns_manifest(self, tmp_path: Path):
        manifest = {"repo_url": "https://github.com/foo/bar", "commit_sha": "deadbeef", "files": []}
        tar = _pack([
            (".scout-manifest.json", json.dumps(manifest).encode("utf-8")),
            ("README.md", b"# Bar"),
        ])
        extracted, got = _extract_tar_safely(tar, tmp_path)
        assert got["commit_sha"] == "deadbeef"
        assert "README.md" in extracted
