"""Round-trip Pydantic models — serialization shape pinned."""

from __future__ import annotations

from web.apps.api.models import AssetDetail, AssetSummary, Stats, StatsResponse


def test_asset_summary_minimum() -> None:
    s = AssetSummary(path="catalog/x.md", bucket="catalog", slug="x")
    d = s.model_dump()
    assert d["path"] == "catalog/x.md"
    assert d["tags"] == []
    assert d["issues"] == []


def test_asset_detail_extends_summary() -> None:
    d = AssetDetail(
        path="catalog/x.md",
        bucket="catalog",
        slug="x",
        body="hello",
    )
    assert d.body == "hello"
    assert d.source is None


def test_stats_serialization() -> None:
    sr = StatsResponse(
        stats=Stats(
            total=3,
            by_bucket={"catalog": 2, "queue": 1},
            by_kind={"repo": 2},
            by_status={"adopted": 1},
            with_issues=0,
        ),
        repo_root="/repo",
        snapshot_mtime=123.0,
    )
    out = sr.model_dump()
    assert out["stats"]["total"] == 3
    assert out["repo_root"] == "/repo"
