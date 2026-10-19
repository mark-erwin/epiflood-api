def test_list_municipalities(client):
    r = client.get("/api/v1/municipalities")
    assert r.status_code == 200
    assert "/api/v1/municipalities" in r.text


def test_get_municipality(client):
    r = client.get("/api/v1/municipalities/PH043404000")
    assert r.status_code == 200
    assert "PH043404000" in r.text


def test_list_morbidity_weeks(client):
    r = client.get("/api/v1/morbidity-weeks")
    assert r.status_code == 200
    assert "morbidity weeks" in r.text
