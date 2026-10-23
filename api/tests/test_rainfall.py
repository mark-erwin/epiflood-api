A = "PH0403401"


def test_weekly_defaults_complete_observed_weeks_only(client):
    body = client.get("/api/v1/rainfall/weekly", params={"pcode": A}).json()
    assert body["total"] == 1
    row = body["data"][0]
    assert (row["year"], row["mw"], row["rain_mm_total"], row["days_with_data"]) == (2025, 1, 70.0, 7)


def test_weekly_min_days_and_forecast_flags(client):
    partial = client.get("/api/v1/rainfall/weekly", params={"pcode": A, "min_days": 3}).json()
    assert [r["mw"] for r in partial["data"]] == [1, 2]
    with_fc = client.get("/api/v1/rainfall/weekly", params={"pcode": A, "include_forecast": True}).json()
    assert [r["mw"] for r in with_fc["data"]] == [1, 3] and with_fc["data"][1]["includes_forecast"] is True


def test_unknown_pcode_is_404_and_bad_range_is_422(client):
    assert client.get("/api/v1/rainfall/weekly", params={"pcode": "PH999"}).status_code == 404
    assert client.get("/api/v1/rainfall/weekly", params={"year_from": 2025, "year_to": 2024}).status_code == 422


def test_daily_and_coverage(client):
    d = client.get("/api/v1/rainfall/daily", params={"pcode": A, "include_forecast": False}).json()
    assert d["total"] == 10
    c = client.get("/api/v1/rainfall/coverage").json()
    assert c["municipalities"] == 1 and c["has_forecast"] is True and c["missing_days"] == 0
