def test_list_queue(client) -> None:
    r = client.get("/queue")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    slugs = {it["slug"] for it in body["items"]}
    assert "fresh-candidate" in slugs
    assert "old-parent" in slugs


def test_get_queue_candidate(client) -> None:
    r = client.get("/queue/fresh-candidate")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "article"
