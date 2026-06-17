def test_list_queue(client) -> None:
    r = client.get("/queue")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "fresh-candidate"


def test_get_queue_candidate(client) -> None:
    r = client.get("/queue/fresh-candidate")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "article"
