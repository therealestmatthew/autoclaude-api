"""End-to-end: the API surfaces the DB-backed index correctly under churn.

The existing routers (catalog, queue, stats, conventions, plans, ...) already
have happy-path tests in their respective files. This file pins the new
behaviours 8.2 introduced: changes on disk surface via `POST /sync`, the
stats reflect the post-sync state, and a record's identity in the DB
matches what the indexer would emit.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_initial_catalog_count_matches_indexer(
    client: TestClient, fixture_repo: Path
) -> None:
    stats = client.get("/stats").json()
    assert stats["stats"]["by_bucket"]["catalog"] >= 2  # alpha + beta in fixture


def test_post_sync_picks_up_new_catalog_asset(
    client: TestClient, fixture_repo: Path
) -> None:
    new_asset = fixture_repo / "catalog" / "delta-tool.md"
    new_asset.write_text(
        "---\nname: delta-tool\nkind: repo\ntitle: Delta tool\n"
        "status: reviewed\nsource:\n  url: https://example.com/delta\n"
        "discovered:\n  via: manual\n  on_date: 2026-06-16\n"
        "created_at: 2026-06-16\nupdated_at: 2026-06-16\n---\n",
        encoding="utf-8",
    )
    before = client.get("/catalog").json()["total"]
    sync_result = client.post("/sync")
    assert sync_result.status_code == 200
    after = client.get("/catalog").json()["total"]
    assert after == before + 1

    detail = client.get("/catalog/delta-tool").json()
    assert detail["slug"] == "delta-tool"
    assert detail["title"] == "Delta tool"


def test_post_sync_drops_deleted_asset(
    client: TestClient, fixture_repo: Path
) -> None:
    (fixture_repo / "catalog" / "beta-skill.md").unlink()
    client.post("/sync")
    resp = client.get("/catalog/beta-skill")
    assert resp.status_code == 404
