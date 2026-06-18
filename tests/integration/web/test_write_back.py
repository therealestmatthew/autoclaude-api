"""End-to-end write-back tests against a real git fixture repo."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _get_asset(client: TestClient, bucket: str, slug: str) -> dict:
    r = client.get(f"/{bucket}/{slug}")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Frontmatter edits
# ---------------------------------------------------------------------------


def test_edit_frontmatter_commits(
    git_client: TestClient, git_fixture_repo: Path
) -> None:
    asset = _get_asset(git_client, "catalog", "alpha-tool")
    new_fm = {
        "name": asset["slug"],
        "kind": asset["kind"],
        "title": "Alpha tool (renamed)",
        "status": asset["status"],
        "source": asset["source"],
        "discovered": asset["discovered"],
        "created_at": asset["created_at"],
        "updated_at": "2026-06-17",
    }
    r = git_client.put(
        f"/catalog/{asset['slug']}/frontmatter",
        json={
            "frontmatter": new_fm,
            "expected_version": asset["version"],
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["commit_sha"]
    assert payload["new_version"] != asset["version"]
    # File on disk has the new title.
    file_path = git_fixture_repo / asset["path"]
    assert "Alpha tool (renamed)" in file_path.read_text()
    # Commit landed.
    log = _git(git_fixture_repo, "log", "-1", "--format=%s")
    assert "edit catalog/alpha-tool" in log


def test_edit_frontmatter_409_on_stale_version(git_client: TestClient) -> None:
    asset = _get_asset(git_client, "catalog", "alpha-tool")
    r = git_client.put(
        f"/catalog/{asset['slug']}/frontmatter",
        json={
            "frontmatter": {"name": asset["slug"], "kind": "repo", "title": "x"},
            "expected_version": "00" * 32,
        },
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["detail"]["code"] == "version-mismatch"


def test_edit_full_writes_both(git_client: TestClient, git_fixture_repo: Path) -> None:
    asset = _get_asset(git_client, "catalog", "alpha-tool")
    r = git_client.put(
        f"/catalog/{asset['slug']}",
        json={
            "frontmatter": {
                "name": asset["slug"],
                "kind": asset["kind"],
                "title": "Alpha (full edit)",
                "status": asset["status"],
                "source": asset["source"],
                "discovered": asset["discovered"],
                "created_at": asset["created_at"],
                "updated_at": "2026-06-17",
            },
            "body": "# new body\n\nrewritten.\n",
            "expected_version": asset["version"],
        },
    )
    assert r.status_code == 200, r.text
    file_text = (git_fixture_repo / asset["path"]).read_text()
    assert "Alpha (full edit)" in file_text
    assert "new body" in file_text


# ---------------------------------------------------------------------------
# Queue triage
# ---------------------------------------------------------------------------


def test_triage_keep_promotes_to_catalog(
    git_client: TestClient, git_fixture_repo: Path
) -> None:
    queue_item = _get_asset(git_client, "queue", "fresh-candidate")
    r = git_client.post(
        f"/queue/{queue_item['slug']}/triage",
        json={
            "action": "keep",
            "expected_version": queue_item["version"],
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["action"] == "keep"
    assert payload["target_path"].startswith("catalog/")
    # Queue file gone, catalog file there.
    assert not (git_fixture_repo / queue_item["path"]).exists()
    target = git_fixture_repo / payload["target_path"]
    assert target.exists()
    assert "status: reviewed" in target.read_text()


def test_triage_discard_requires_notes(git_client: TestClient) -> None:
    queue_item = _get_asset(git_client, "queue", "fresh-candidate")
    r = git_client.post(
        f"/queue/{queue_item['slug']}/triage",
        json={
            "action": "discard",
            "expected_version": queue_item["version"],
        },
    )
    assert r.status_code == 422, r.text


def test_triage_discard_with_notes(
    git_client: TestClient, git_fixture_repo: Path
) -> None:
    queue_item = _get_asset(git_client, "queue", "fresh-candidate")
    r = git_client.post(
        f"/queue/{queue_item['slug']}/triage",
        json={
            "action": "discard",
            "expected_version": queue_item["version"],
            "notes": "Off-topic; not catalogable.",
        },
    )
    assert r.status_code == 200, r.text
    assert not (git_fixture_repo / queue_item["path"]).exists()
    log = _git(git_fixture_repo, "log", "-1", "--format=%s")
    assert "triage discard" in log


def test_triage_merge_into_existing(
    git_client: TestClient, git_fixture_repo: Path
) -> None:
    queue_item = _get_asset(git_client, "queue", "fresh-candidate")
    r = git_client.post(
        f"/queue/{queue_item['slug']}/triage",
        json={
            "action": "merge",
            "target_slug": "alpha-tool",
            "expected_version": queue_item["version"],
        },
    )
    assert r.status_code == 200, r.text
    target = git_fixture_repo / "catalog" / "alpha-tool.md"
    text = target.read_text()
    assert "## From queue" in text
    assert not (git_fixture_repo / queue_item["path"]).exists()


def test_triage_keep_409_on_stale_version(git_client: TestClient) -> None:
    queue_item = _get_asset(git_client, "queue", "fresh-candidate")
    r = git_client.post(
        f"/queue/{queue_item['slug']}/triage",
        json={
            "action": "keep",
            "expected_version": "00" * 32,
        },
    )
    assert r.status_code == 409, r.text


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------


def test_proposal_create_accept_lifecycle(
    git_client: TestClient, git_fixture_repo: Path
) -> None:
    queue_item = _get_asset(git_client, "queue", "fresh-candidate")
    # Create a proposal as if the reviewer agent had posted it.
    p = git_client.post(
        "/proposals",
        json={
            "source": "reviewer-agent",
            "target_path": queue_item["path"],
            "target_bucket": "queue",
            "action_kind": "keep",
            "payload": {"target_slug": "fresh-candidate"},
            "summary": "Promote to catalog.",
            "rationale": "Looks high-quality.",
            "confidence": 0.85,
        },
    )
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    # Accept the proposal.
    a = git_client.post(f"/proposals/{pid}/accept", json={})
    assert a.status_code == 200, a.text
    assert a.json()["action"] == "keep"
    # The proposal is now accepted.
    d = git_client.get(f"/proposals/{pid}")
    assert d.json()["status"] == "accepted"


def test_proposal_reject_records_audit(git_client: TestClient) -> None:
    queue_item = _get_asset(git_client, "queue", "fresh-candidate")
    p = git_client.post(
        "/proposals",
        json={
            "source": "reviewer-agent",
            "target_path": queue_item["path"],
            "target_bucket": "queue",
            "action_kind": "discard",
            "payload": {"notes": "spam"},
            "summary": "Discard as spam.",
            "rationale": "...",
            "confidence": 0.3,
        },
    )
    pid = p.json()["id"]
    r = git_client.post(f"/proposals/{pid}/reject", json={"notes": "actually looks fine"})
    assert r.status_code == 200, r.text
    d = git_client.get(f"/proposals/{pid}").json()
    assert d["status"] == "rejected"
    assert d["decision_audit_id"]


# ---------------------------------------------------------------------------
# Regression tests for the gitignored-queue bug (surfaced during 8.3 dogfood)
# ---------------------------------------------------------------------------


def test_triage_keep_with_gitignored_queue(
    git_client: TestClient, git_fixture_repo: Path
) -> None:
    """Real-world: the main repo's .gitignore covers scout/queue/*.md so
    queue files are never tracked. The triage keep should:
      - delete the source queue file (safe; it was untracked)
      - create + commit the new catalog file
      - NOT 500 on `git add` against the untracked source.

    The fixture's .gitignore un-ignores everything (`!*`); we layer a
    gitignore line on top of it and re-commit, so this single test
    captures the production behavior.
    """
    # Layer a queue-gitignore on top of the fixture's `!*`.
    gitignore = git_fixture_repo / ".gitignore"
    text = gitignore.read_text() if gitignore.exists() else ""
    gitignore.write_text(text + "\n/scout/queue/*.md\n")
    _git(git_fixture_repo, "add", ".gitignore")
    _git(
        git_fixture_repo,
        "-c", "user.email=t@x", "-c", "user.name=t",
        "commit", "-q", "-m", "gitignore queue",
    )
    # Confirm the fixture queue file is now untracked.
    queue_path = "scout/queue/2026-06-15-fresh-candidate-abcd1234.md"
    _git(git_fixture_repo, "rm", "--cached", "-q", queue_path)
    _git(
        git_fixture_repo,
        "-c", "user.email=t@x", "-c", "user.name=t",
        "commit", "-q", "-m", "untrack queue",
    )

    # Re-sync so the API picks up the now-untracked file's version.
    git_client.post("/sync")

    queue_item = git_client.get("/queue/fresh-candidate").json()
    r = git_client.post(
        f"/queue/{queue_item['slug']}/triage",
        json={"action": "keep", "expected_version": queue_item["version"]},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    # The catalog file landed AND a new commit was made.
    catalog_target = git_fixture_repo / "catalog" / "fresh-candidate.md"
    assert catalog_target.exists()
    assert payload["commit_sha"]
    log = subprocess.run(
        ["git", "log", "-1", "--name-only", "--format=%H"],
        cwd=str(git_fixture_repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "catalog/fresh-candidate.md" in log
    assert payload["commit_sha"] == log.splitlines()[0]


def test_triage_discard_with_gitignored_queue(
    git_client: TestClient, git_fixture_repo: Path
) -> None:
    """Discard of a gitignored queue file: file deleted, audit row stays
    in `committed`, NO new git commit (nothing tracked to commit)."""
    gitignore = git_fixture_repo / ".gitignore"
    text = gitignore.read_text() if gitignore.exists() else ""
    gitignore.write_text(text + "\n/scout/queue/*.md\n")
    _git(git_fixture_repo, "add", ".gitignore")
    _git(
        git_fixture_repo,
        "-c", "user.email=t@x", "-c", "user.name=t",
        "commit", "-q", "-m", "gitignore queue",
    )
    _git(
        git_fixture_repo, "rm", "--cached", "-q",
        "scout/queue/2026-06-15-fresh-candidate-abcd1234.md",
    )
    _git(
        git_fixture_repo,
        "-c", "user.email=t@x", "-c", "user.name=t",
        "commit", "-q", "-m", "untrack queue",
    )

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(git_fixture_repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    git_client.post("/sync")
    queue_item = git_client.get("/queue/fresh-candidate").json()
    r = git_client.post(
        f"/queue/{queue_item['slug']}/triage",
        json={
            "action": "discard",
            "expected_version": queue_item["version"],
            "notes": "test discard",
        },
    )
    assert r.status_code == 200, r.text
    # No new commit; HEAD unchanged.
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(git_fixture_repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head_after == head_before
    # Queue file deleted from disk.
    assert not (
        git_fixture_repo / "scout/queue/2026-06-15-fresh-candidate-abcd1234.md"
    ).exists()


def test_proposal_list_filters(git_client: TestClient) -> None:
    git_client.post(
        "/proposals",
        json={
            "source": "operator",
            "target_path": "scout/queue/fake.md",
            "target_bucket": "queue",
            "action_kind": "discard",
            "payload": {},
            "summary": "x",
            "rationale": "x",
        },
    )
    pending = git_client.get("/proposals?status=pending").json()
    assert pending["total"] >= 1
    operator = git_client.get("/proposals?source=operator").json()
    assert operator["total"] >= 1
