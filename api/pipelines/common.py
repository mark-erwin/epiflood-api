"""Shared paths and constants for the ingestion pipelines.

Run everything from inside api/:  python -m pipelines.run_all

Folder layout (inputs you place by hand, outputs the pipelines write):

    data/epidemiology/
        doh-epi-dengue-data-2016-2021.csv      HDX dengue (input)
        eb/dengue/*.csv, eb/leptospirosis/*.csv  raw DOH EB weekly reports (input, option A)
        laguna_bgy_pcode_<disease>_clusters.csv  staged cluster files (input, option B)
        processed/                              staging CSVs (output)
    data/gis/
        phl_admin3.geojson, phl_admin4.geojson   national admin boundaries (input)
        laguna_municipality_geodata.geojson      or pre-filtered Laguna files (input, fallback)
        laguna_barangay_geodata.geojson
        laguna_floodhazard_5year.gpkg            Project NOAH hazard (input, preferred)
        flood5year/Laguna_Flood_5year.shp        same hazard layer (input, fallback)
        health_facilities.geojson                health facility points (input, map table)
        laguna_pcode_lookup.csv                  written by ingest_boundaries, loaded into pcode_lookup
        processed/                              cleaned geodata and the hazard CSV (output)
    data/rainfall/
        laguna_weekly_rainfall.csv              export from the database (output)
"""

import logging
from pathlib import Path

from core.config import EPI_DIR, GIS_DIR, RAIN_DIR      # data folders are defined once, in core/config.py
from db.connect import API_ROOT, DB_PATH, connect  # noqa: F401  (re-exported for the pipelines)
from db.init_db import SCHEMA_SQL, init_schema  # noqa: F401

log = logging.getLogger("pipelines")

# ---- folders (EPI_DIR, GIS_DIR, RAIN_DIR come from core/config.py) ---------
EPI_OUT = EPI_DIR / "processed"
GIS_OUT = GIS_DIR / "processed"

# ---- input files -----------------------------------------------------------
ADMIN3_PATH = GIS_DIR / "phl_admin3.geojson"
ADMIN4_PATH = GIS_DIR / "phl_admin4.geojson"
LAGUNA_ADM3_PATH = GIS_DIR / "laguna_municipality_geodata.geojson"   # already filtered to Laguna
LAGUNA_ADM4_PATH = GIS_DIR / "laguna_barangay_geodata.geojson"
HAZARD_GPKG_PATH = GIS_DIR / "laguna_floodhazard_5year.gpkg"          # preferred: same file the map tables load
HAZARD_PATH = GIS_DIR / "flood5year" / "Laguna_Flood_5year.shp"       # fallback
HEALTH_FACILITIES_PATH = GIS_DIR / "health_facilities.geojson"

HDX_DENGUE_PATH = EPI_DIR / "doh-epi-dengue-data-2016-2021.csv"
EB_DIR = EPI_DIR / "eb"
EB_STAGED = {
    "dengue": EPI_DIR / "laguna_bgy_pcode_dengue_clusters.csv",
    "leptospirosis": EPI_DIR / "laguna_bgy_pcode_leptospirosis_clusters.csv",
}

OVERRIDES_PATH = API_ROOT / "pipelines" / "crosswalk" / "municipality_overrides.csv"
PCODE_LOOKUP_PATH = GIS_DIR / "laguna_pcode_lookup.csv"             # read by db/init_db.py load_pcode_lookup

# ---- constants -------------------------------------------------------------
PROVINCE = "Laguna"
REGION = "Region IV-A"
EXPECTED_LAGUNA_LGUS = 30            # 6 cities + 24 municipalities
TARGET_CRS = "EPSG:32651"            # UTM 51N, used for all area/length maths
DISEASES = ("dengue", "leptospirosis")
