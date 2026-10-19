def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "X-Request-ID" in r.headers


def test_invalid_disease_returns_shared_error_shape(client):
    r = client.get("/api/v1/map/cases/measles")
    assert r.status_code == 422
    assert set(r.json()) == {"error", "detail", "request_id"}
