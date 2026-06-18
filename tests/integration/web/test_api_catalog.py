"""Catalog router integration tests against the fixture repo."""

from __future__ import annotations


def test_list_catalog(client) -> None:
    r = client.get("/catalog")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    slugs = {item["slug"] for item in body["items"]}
    assert {"alpha-tool", "beta-skill", "child-a", "child-b"} <= slugs


def test_get_catalog_asset(client) -> None:
    r = client.get("/catalog/alpha-tool")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "alpha-tool"
    assert body["kind"] == "repo"
    assert "alpha-tool" in body["body"]
    assert body["source"]["url"].startswith("https://github.com/example/")


def test_get_missing_catalog_asset(client) -> None:
    r = client.get("/catalog/does-not-exist")
    assert r.status_code == 404


def test_filter_by_kind(client) -> None:
    r = client.get("/catalog?kind=skill")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    slugs = {it["slug"] for it in items}
    assert "beta-skill" in slugs
    assert "child-b" in slugs


def test_search_substring(client) -> None:
    r = client.get("/catalog?q=alpha")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(it["slug"] == "alpha-tool" for it in items)
