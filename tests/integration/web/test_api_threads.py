def test_threads_for_specific_day(client) -> None:
    r = client.get("/threads?date=2026-06-15")
    assert r.status_code == 200
    body = r.json()
    # 3 valid lines, 1 invalid -> 3 events parsed
    assert body["total"] == 3
    agents = {e["agent"] for e in body["events"]}
    assert {"scout", "scout-dedup", "scout-extract-repo"} <= agents


def test_threads_filter_by_agent(client) -> None:
    r = client.get("/threads?date=2026-06-15&agent=scout-dedup")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["events"][0]["agent"] == "scout-dedup"


def test_threads_filter_by_outcome(client) -> None:
    r = client.get("/threads?date=2026-06-15&outcome=partial")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1


def test_threads_missing_day_empty(client) -> None:
    r = client.get("/threads?date=2024-01-01")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
