"""Tests for the sha256 fingerprint scheme."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

from scout.agent.types import RepoExtractRequest
from scout.extractors.repo import RepoExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "repo-clones"


def _tar_with_manifest_shas(repo_url: str) -> bytes:
    """Pack minimal-with-agent + a manifest carrying the *correct* sha so we
    can verify the extractor trusts the manifest rather than recomputing."""
    src = FIXTURES / "minimal-with-agent"
    files = []
    paths = sorted(p for p in src.rglob("*") if p.is_file())

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for p in paths:
            rel = str(p.relative_to(src))
            data = p.read_bytes()
            files.append({
                "relpath": rel,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
            tf.add(p, arcname=rel)

        manifest = {
            "repo_url": repo_url,
            "commit_sha": "cafef00d",
            "files": files,
            "warnings": [],
        }
        mb = json.dumps(manifest).encode("utf-8")
        info = tarfile.TarInfo(name=".scout-manifest.json")
        info.size = len(mb)
        tf.addfile(info, io.BytesIO(mb))
    return buf.getvalue()


def test_fingerprint_matches_file_bytes():
    expected = hashlib.sha256(
        (FIXTURES / "minimal-with-agent" / ".claude" / "agents" / "code-reviewer.md").read_bytes()
    ).hexdigest()

    ext = RepoExtractor(fetch_tar=_tar_with_manifest_shas)
    report = ext.extract(RepoExtractRequest(
        repo_slug="fp-test", repo_url="https://github.com/foo/bar", run_id="r1",
    ))
    assert len(report.candidates) == 1
    assert report.candidates[0].fingerprint == f"sha256:{expected}"


def test_fingerprint_falls_back_to_host_hash_when_manifest_empty():
    """If the manifest has no files block, the extractor still computes the
    hash itself from the bytes on disk."""
    def _fetch(repo_url: str) -> bytes:
        src = FIXTURES / "minimal-with-agent"
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for p in sorted(src.rglob("*")):
                if p.is_file():
                    tf.add(p, arcname=str(p.relative_to(src)))
            mb = json.dumps({
                "repo_url": repo_url, "commit_sha": "deadbeef",
                "files": [], "warnings": [],
            }).encode("utf-8")
            info = tarfile.TarInfo(name=".scout-manifest.json")
            info.size = len(mb)
            tf.addfile(info, io.BytesIO(mb))
        return buf.getvalue()

    ext = RepoExtractor(fetch_tar=_fetch)
    report = ext.extract(RepoExtractRequest(
        repo_slug="fp-fallback", repo_url="https://github.com/foo/bar", run_id="r1",
    ))
    expected = hashlib.sha256(
        (FIXTURES / "minimal-with-agent" / ".claude" / "agents" / "code-reviewer.md").read_bytes()
    ).hexdigest()
    assert report.candidates[0].fingerprint == f"sha256:{expected}"
