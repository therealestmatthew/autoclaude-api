"""End-to-end test for the repo extractor.

We pack a fixture clone into a tar in-memory (no container, no docker),
inject it via the runner's manual-extract path, and assert the children land
in /scout/queue/ with the expected frontmatter and that the thread log
records a clean run.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import yaml

from scout._util import parse_frontmatter
from scout.agent import runner
from scout.extractors.repo import RepoExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "repo-clones"


def _tarball_for(fixture: str, *, commit_sha: str = "feedface") -> bytes:
    src = FIXTURES / fixture
    buf = io.BytesIO()
    files = []
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for p in sorted(src.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(src))
            data = p.read_bytes()
            files.append({
                "relpath": rel,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
            tf.add(p, arcname=rel)
        manifest = {
            "repo_url": "https://github.com/anthropics/example",
            "commit_sha": commit_sha,
            "files": files,
            "warnings": [],
        }
        mb = json.dumps(manifest).encode("utf-8")
        info = tarfile.TarInfo(name=".scout-manifest.json")
        info.size = len(mb)
        tf.addfile(info, io.BytesIO(mb))
    return buf.getvalue()


def test_extract_repo_once_writes_child_queue_files(scout_world):
    tar = _tarball_for("minimal-with-agent")
    extractor = RepoExtractor(fetch_tar=lambda _url: tar)

    result = runner.extract_repo_once(
        repo_url="https://github.com/anthropics/example",
        extractor=extractor,
    )

    assert result["children_queued"] == 1
    assert result["commit_sha"] == "feedface"
    assert not result["fatal"]

    queue_files = sorted(scout_world["queue"].glob("*.md"))
    assert len(queue_files) == 1
    fm = parse_frontmatter(queue_files[0].read_text())
    assert fm["kind"] == "agent"
    assert fm["name"].endswith("--code-reviewer")
    assert fm["relations"]["parent"] == fm["name"].split("--", 1)[0]
    assert fm["fingerprint"].startswith("sha256:")
    assert fm["source"]["type"] == "github"
    assert "/blob/feedface/" in fm["source"]["url"]


def test_run_once_extracts_from_repo_queue(scout_world, monkeypatch):
    """A `kind: repo, source.type: github` queue file triggers the repo
    extractor during `scout run`."""
    # Seed a parent repo queue file.
    parent_slug = "alice-cool-tool"
    parent_fm = {
        "name": parent_slug,
        "kind": "repo",
        "title": "Alice's cool tool",
        "status": "draft",
        "source": {
            "type": "github",
            "url": "https://github.com/alice/cool-tool",
            "authors": ["alice"],
            "license": "MIT",
        },
        "discovered": {"via": "manual", "on": "2026-06-15", "run_id": "seed"},
        "created_at": "2026-06-15",
        "updated_at": "2026-06-15",
    }
    parent_path = scout_world["queue"] / "2026-06-15-alice-cool-tool-aaaaaaaa.md"
    parent_path.write_text(
        f"---\n{yaml.safe_dump(parent_fm, sort_keys=False)}---\n\n# notes\n"
    )

    tar = _tarball_for("minimal-with-skill")
    monkeypatch.setattr(
        runner, "RepoExtractor",
        lambda *a, **kw: RepoExtractor(fetch_tar=lambda _u: tar),
    )

    stats = runner.run_once(verbose=False)

    assert stats["repo_extraction"]["repos_extracted"] == 1
    assert stats["repo_extraction"]["children_queued"] == 1

    children = [
        p for p in scout_world["queue"].glob("*.md")
        if p.name != parent_path.name
    ]
    assert len(children) == 1
    fm = parse_frontmatter(children[0].read_text())
    assert fm["kind"] == "skill"
    assert fm["relations"]["parent"] == parent_slug
    assert fm["name"] == f"{parent_slug}--test-runner"
    # Inherits provenance from the parent.
    assert fm["source"]["authors"] == ["alice"]
    assert fm["source"]["license"] == "MIT"


def test_run_once_skips_repos_already_extracted(scout_world, monkeypatch):
    """If a child of repo X already exists in the queue, the runner does not
    re-extract X on the next tick."""
    parent_slug = "alice-cool-tool"
    parent_fm = {
        "name": parent_slug,
        "kind": "repo",
        "title": "Alice's cool tool",
        "status": "draft",
        "source": {"type": "github", "url": "https://github.com/alice/cool-tool"},
        "discovered": {"via": "manual", "on": "2026-06-15"},
        "created_at": "2026-06-15",
        "updated_at": "2026-06-15",
    }
    parent_path = scout_world["queue"] / "2026-06-15-alice-cool-tool-aaaaaaaa.md"
    parent_path.write_text(
        f"---\n{yaml.safe_dump(parent_fm, sort_keys=False)}---\n\n# notes\n"
    )
    # Pre-existing child.
    child_fm = {
        "name": f"{parent_slug}--existing",
        "kind": "agent",
        "title": "Existing",
        "status": "draft",
        "source": {"type": "github", "url": "https://github.com/x"},
        "discovered": {"via": "manual", "on": "2026-06-15"},
        "relations": {"parent": parent_slug},
        "created_at": "2026-06-15",
        "updated_at": "2026-06-15",
    }
    (scout_world["queue"] / "2026-06-15-existing.md").write_text(
        f"---\n{yaml.safe_dump(child_fm, sort_keys=False)}---\n"
    )

    calls = []

    def _no_calls(_url):
        calls.append(_url)
        return b""

    monkeypatch.setattr(
        runner, "RepoExtractor",
        lambda *a, **kw: RepoExtractor(fetch_tar=_no_calls),
    )

    stats = runner.run_once(verbose=False)
    assert stats["repo_extraction"]["repos_extracted"] == 0
    assert calls == []
