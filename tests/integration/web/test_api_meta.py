def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["records"] > 0


def test_stats(client) -> None:
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()["stats"]
    assert body["by_bucket"].get("catalog") == 4
    assert body["by_bucket"].get("queue") == 2


def test_sync_forces_rebuild(client) -> None:
    r = client.post("/sync")
    assert r.status_code == 200
    assert r.json()["rebuilt"] is True


def test_search(client) -> None:
    r = client.get("/search?q=alpha")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(h["slug"] == "alpha-tool" for h in body["hits"])


def test_engagements(client) -> None:
    r = client.get("/engagements")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "2026-acme"


def test_conventions(client) -> None:
    r = client.get("/conventions")
    assert r.status_code == 200
    body = r.json()
    assert any(it["slug"] == "convention-naming" for it in body["items"])


def test_plans(client) -> None:
    r = client.get("/plans")
    assert r.status_code == 200
    body = r.json()
    assert any(it["slug"] == "phase-1-fixture" for it in body["items"])
