"""Fixture database: schema.sql in memory + a tiny hand-checkable dataset. No spatial extension needed."""

import json
from datetime import timedelta
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from api.api import app
from utils.morbidity_week import mw_range

SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
A, B = "PH0403401", "PH0403402"      # Alaminos, Bay
SQUARE = lambda x: json.dumps({"type": "Polygon", "coordinates": [[[x, 14], [x + 1, 14], [x + 1, 15], [x, 15], [x, 14]]]})


@pytest.fixture(scope="session")
def fixture_db():
    con = duckdb.connect(":memory:")
    con.execute(SCHEMA.read_text())
    con.execute("INSERT INTO municipalities (pcode, name, type, boundary_geojson) VALUES (?, 'Alaminos', 'municipality', ?), (?, 'Bay', 'municipality', ?)",
                [A, SQUARE(121), B, SQUARE(122)])
    for year in (2024, 2025):
        for mw in (1, 2, 3):
            s, e = mw_range(year, mw)
            con.execute("INSERT INTO morbidity_weeks VALUES (?, ?, ?, ?)", [year, mw, s, e])
    # dengue: A reports in 2024 MW2 (=10) and 2025 MW2 (=20); B reports nothing -> NULL on the map
    con.execute("INSERT INTO cases_weekly (pcode, disease, year, mw, cases, deaths, source) VALUES "
                "(?, 'dengue', 2024, 2, 10, 0, 'doh_eb'), (?, 'dengue', 2025, 2, 20, 1, 'doh_eb'), (?, 'dengue', 2025, 3, 0, 0, 'doh_eb')",
                [A, A, A])
    # rainfall for A: 2025 MW1 complete (7 x 10 mm), MW2 partial (3 days), MW3 complete but forecast
    s1, _ = mw_range(2025, 1); s2, _ = mw_range(2025, 2); s3, _ = mw_range(2025, 3)
    rows = [(A, s1 + timedelta(d), 10.0, False) for d in range(7)]
    rows += [(A, s2 + timedelta(d), 5.0, False) for d in range(3)]
    rows += [(A, s3 + timedelta(d), 1.0, True) for d in range(7)]
    con.executemany("INSERT INTO rainfall_daily (pcode, date, rain_mm, is_forecast) VALUES (?, ?, ?, ?)", rows)
    return con


@pytest.fixture
def client(fixture_db):
    app.state.db = fixture_db          # TestClient without a `with` block skips lifespan
    return TestClient(app)
