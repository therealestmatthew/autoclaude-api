"""Tests for the <repo>--<child> slug scoping + collision handling."""

from __future__ import annotations

from pathlib import Path

from scout.agent.types import RepoExtractRequest
from scout.extractors.repo import RepoExtractor

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "repo-clones"


def _make_extractor(fixture: str) -> RepoExtractor:
    """Build a RepoExtractor whose 'tar fetch' streams the fixture directory
    as a tar in memory. Bypasses the container entirely."""
    import io
    import tarfile

    src = FIXTURES / fixture

    def _fake_fetch(repo_url: str) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for path in sorted(src.rglob("*")):
                if not path.is_file():
                    continue
                tf.add(path, arcname=str(path.relative_to(src)))
            # Tack on a manifest.
            import json
            manifest = {
                "repo_url": repo_url,
                "commit_sha": "abc123",
                "files": [],
                "warnings": [],
            }
            data = json.dumps(manifest).encode("utf-8")
            info = tarfile.TarInfo(name=".scout-manifest.json")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    return RepoExtractor(fetch_tar=_fake_fetch)


def _req(slug: str = "minimal-test", url: str = "https://github.com/foo/bar") -> RepoExtractRequest:
    return RepoExtractRequest(repo_slug=slug, repo_url=url, run_id="scout-test-run")


def test_agent_slug_is_scoped_under_repo():
    report = _make_extractor("minimal-with-agent").extract(_req())
    assert len(report.candidates) == 1
    c = report.candidates[0]
    assert c.kind == "agent"
    assert c.name == "minimal-test--code-reviewer"
    assert c.parent == "minimal-test"
    assert c.fingerprint.startswith("sha256:")


def test_skill_slug_uses_directory_name():
    report = _make_extractor("minimal-with-skill").extract(_req())
    assert len(report.candidates) == 1
    c = report.candidates[0]
    assert c.kind == "skill"
    assert c.name == "minimal-test--test-runner"


def test_mcp_emits_one_candidate_per_server_entry():
    report = _make_extractor("mcp-server-config").extract(_req())
    kinds = {c.kind for c in report.candidates}
    slugs = sorted(c.name for c in report.candidates)
    assert kinds == {"mcp"}
    assert slugs == ["minimal-test--mcp-github", "minimal-test--mcp-supabase"]


def test_prompt_requires_explicit_frontmatter():
    report = _make_extractor("with-prompts").extract(_req())
    assert len(report.candidates) == 1
    assert report.candidates[0].kind == "prompt"
    assert report.candidates[0].name == "minimal-test--triage"


def test_source_url_points_at_commit_blob():
    report = _make_extractor("minimal-with-agent").extract(_req())
    c = report.candidates[0]
    assert c.source_url == (
        "https://github.com/foo/bar/blob/abc123/.claude/agents/code-reviewer.md"
    )


def test_duplicate_child_slug_warns_and_emits_first(tmp_path: Path):
    """Two agents that would slug-collide: agents/foo.md and .claude/agents/foo.md."""
    import io
    import json
    import tarfile

    def _fake_fetch(repo_url: str) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for name, content in [
                (".claude/agents/foo.md", b"# claude-scope foo"),
                ("agents/foo.md", b"# top-level foo"),
            ]:
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))
            manifest = json.dumps({
                "repo_url": repo_url, "commit_sha": "deadbeef",
                "files": [], "warnings": [],
            }).encode("utf-8")
            info = tarfile.TarInfo(name=".scout-manifest.json")
            info.size = len(manifest)
            tf.addfile(info, io.BytesIO(manifest))
        return buf.getvalue()

    ext = RepoExtractor(fetch_tar=_fake_fetch)
    report = ext.extract(_req())
    # Only the first wins.
    slugs = [c.name for c in report.candidates]
    assert slugs == ["minimal-test--foo"]
    assert any("duplicate-child-slug" in w for w in report.warnings)
