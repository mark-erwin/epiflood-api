from middleware.cache_headers import cache_control_for


def test_rules():
    assert cache_control_for("/api/v1/map/boundaries") == "public, max-age=86400, stale-while-revalidate=8640"
    assert cache_control_for("/api/v1/map/cases").startswith("public, max-age=900")
    assert cache_control_for("/api/v1/health") == "no-store"
    assert cache_control_for("/docs") is None
    assert cache_control_for("/api/v1/mapping") is None


def test_errors_are_not_cached(client):
    r = client.get("/api/v1/rainfall/weekly", params={"pcode": "PH999"})
    assert r.status_code == 404 and "cache-control" not in r.headers
