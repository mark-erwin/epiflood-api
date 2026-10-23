def test_list_municipalities(client):
    r = client.get("/api/v1/municipalities")
    assert r.status_code == 200
    assert {m["pcode"] for m in r.json()} == {"PH0403401", "PH0403402"}


def test_get_municipality(client):
    r = client.get("/api/v1/municipalities/PH0403401")
    assert r.status_code == 200
    assert r.json()["name"] == "Alaminos"
    assert client.get("/api/v1/municipalities/PH0403499").status_code == 404


def test_list_morbidity_weeks(client):
    body = client.get("/api/v1/morbidity-weeks").json()
    assert body["earliest"] == {"year": 2024, "mw": 2}
    assert body["latest"] == {"year": 2025, "mw": 3}