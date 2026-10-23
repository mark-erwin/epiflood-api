import json

from services import map_service

A, B = "PH0403401", "PH0403402"


def by_pcode(fc):
    return {f["properties"]["pcode"]: f["properties"] for f in fc["features"]}


def test_layer_catalogue_lists_five_layers(client):
    assert [l["layer"] for l in client.get("/api/v1/map/layers").json()] == [0, 1, 2, 3, 4]


def test_boundaries_with_and_without_geometry(client):
    fc = client.get("/api/v1/map/boundaries").json()
    assert len(fc["features"]) == 2 and fc["features"][0]["geometry"]["type"] == "Polygon"
    assert client.get("/api/v1/map/boundaries", params={"geometry": False}).json()["features"][0]["geometry"] is None


def test_cases_default_is_latest_reported_week_and_null_is_not_zero(client):
    fc = client.get("/api/v1/map/cases", params={"disease": "dengue"}).json()
    assert (fc["metadata"]["year"], fc["metadata"]["mw"]) == (2025, 3)   # MW3 has cases = 0, which counts as reported
    p = by_pcode(fc)
    assert p[A]["cases"] == 0 and p[A]["reported"] is True
    assert p[B]["cases"] is None and p[B]["reported"] is False


def test_cases_ratio_to_baseline(client):
    p = by_pcode(client.get("/api/v1/map/cases", params={"disease": "dengue", "year": 2025, "mw": 2}).json())
    assert p[A]["cases"] == 20 and p[A]["baseline_mean"] == 10 and p[A]["ratio_to_baseline"] == 2.0


def test_cases_needs_both_year_and_mw_and_data(client):
    assert client.get("/api/v1/map/cases", params={"disease": "dengue", "year": 2025}).status_code == 422
    assert client.get("/api/v1/map/cases", params={"disease": "leptospirosis"}).status_code == 404


def test_baseline_layer(client):
    fc = client.get("/api/v1/map/baseline", params={"mw": 2}).json()
    assert fc["metadata"]["baseline_years"] == [2020, 2024]
    assert by_pcode(fc)[A]["mean_cases"] == 10 and by_pcode(fc)[B]["mean_cases"] is None


def test_hazard_serves_file_or_503(client, tmp_path, monkeypatch):
    monkeypatch.setitem(map_service.HAZARD_FILES, "low", tmp_path / "missing.geojson")
    assert client.get("/api/v1/map/hazard").status_code == 503
    f = tmp_path / "h.geojson"; f.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    monkeypatch.setitem(map_service.HAZARD_FILES, "low", f)
    r = client.get("/api/v1/map/hazard")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/geo+json")
    assert "max-age=86400" in r.headers["cache-control"]
