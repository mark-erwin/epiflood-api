-- =====================================================================
-- EpiFlood API: DuckDB schema (example)
-- Place at: api/db/schema.sql  (no ML/prediction tables: the project is analysis-only)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Reference tables
-- ---------------------------------------------------------------------

-- Laguna cities/municipalities (HDX Subnational Administrative Boundaries)
CREATE TABLE IF NOT EXISTS municipalities (
    pcode            VARCHAR PRIMARY KEY,          -- administrative code, e.g. 'PH043404000'
    name             VARCHAR NOT NULL,             -- e.g. 'Calamba City'
    type             VARCHAR NOT NULL CHECK (type IN ('city', 'municipality')),
    province         VARCHAR NOT NULL DEFAULT 'Laguna',
    region           VARCHAR NOT NULL DEFAULT 'Region IV-A',
    centroid_lng     DOUBLE,                       -- used for Open-Meteo queries
    centroid_lat     DOUBLE,
    area_km2         DOUBLE,
    boundary_geojson VARCHAR                       -- geometry as GeoJSON text (Layer 1)
);

-- Maps raw names found in DOH sheets to a PCode
CREATE TABLE IF NOT EXISTS municipality_crosswalk (
    raw_name VARCHAR NOT NULL,                     -- e.g. 'CITY OF CALAMBA'
    source   VARCHAR NOT NULL,                     -- 'doh_hdx' | 'doh_eb'
    pcode    VARCHAR NOT NULL REFERENCES municipalities(pcode),
    PRIMARY KEY (raw_name, source)
);

-- Barangay -> municipality lookup (built from the adm4 boundary file, loaded by db/init_db.py)
CREATE TABLE IF NOT EXISTS pcode_lookup (
    barangay_pcode     VARCHAR PRIMARY KEY,
    barangay_name      VARCHAR NOT NULL,
    municipality_pcode VARCHAR NOT NULL,
    municipality_name  VARCHAR NOT NULL
);

-- One row per morbidity week, so MW <-> date logic lives in one place
CREATE TABLE IF NOT EXISTS morbidity_weeks (
    year       INTEGER NOT NULL,
    mw         INTEGER NOT NULL CHECK (mw BETWEEN 1 AND 53),
    week_start DATE NOT NULL,
    week_end   DATE NOT NULL,
    PRIMARY KEY (year, mw)
);

-- ---------------------------------------------------------------------
-- 2. Epidemiological data
-- ---------------------------------------------------------------------

-- Consolidated weekly cases (HDX 2016-2021 + DOH EB weekly reports 2021-2026)
CREATE TABLE IF NOT EXISTS cases_weekly (
    pcode    VARCHAR NOT NULL REFERENCES municipalities(pcode),
    disease  VARCHAR NOT NULL CHECK (disease IN ('dengue', 'leptospirosis')),
    year     INTEGER NOT NULL,
    mw       INTEGER NOT NULL CHECK (mw BETWEEN 1 AND 53),
    cases    INTEGER,                              -- NULL = not reported, 0 = reported zero
    deaths   INTEGER,
    source   VARCHAR NOT NULL,                     -- 'doh_hdx' | 'doh_eb'
    ingested_at TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (pcode, disease, year, mw)
);

-- Province-level weekly cases. Filled only when a source (e.g. the HDX 2016-2021
-- dengue file) has no municipality breakdown.
CREATE TABLE IF NOT EXISTS cases_province_weekly (
    province VARCHAR NOT NULL,
    disease  VARCHAR NOT NULL CHECK (disease IN ('dengue', 'leptospirosis')),
    year     INTEGER NOT NULL,
    mw       INTEGER NOT NULL CHECK (mw BETWEEN 1 AND 53),
    cases    INTEGER,
    deaths   INTEGER,
    source   VARCHAR NOT NULL,
    PRIMARY KEY (province, disease, year, mw)
);

-- ---------------------------------------------------------------------
-- 3. Environmental data (map polygons live in flood_hazards, created by db/init_db.py)
-- ---------------------------------------------------------------------

-- Open-Meteo historical + forecast rainfall at municipality centroids
CREATE TABLE IF NOT EXISTS rainfall_daily (
    pcode   VARCHAR NOT NULL REFERENCES municipalities(pcode),
    date    DATE NOT NULL,
    rain_mm DOUBLE,
    is_forecast BOOLEAN NOT NULL DEFAULT FALSE,
    source  VARCHAR NOT NULL DEFAULT 'open_meteo',
    PRIMARY KEY (pcode, date)
);

-- Precomputed: share of each municipality covered by each hazard level
CREATE TABLE IF NOT EXISTS hazard_by_municipality (
    pcode        VARCHAR NOT NULL REFERENCES municipalities(pcode),
    hazard_level INTEGER NOT NULL CHECK (hazard_level BETWEEN 1 AND 3),
    area_km2     DOUBLE NOT NULL,
    pct_of_area  DOUBLE NOT NULL,                  -- 0-100
    PRIMARY KEY (pcode, hazard_level)
);

-- ---------------------------------------------------------------------
-- 4. Metadata (feeds /sources and /schema)
-- ---------------------------------------------------------------------

-- Data inventory (Appendix B)
CREATE TABLE IF NOT EXISTS data_sources (
    source_id        VARCHAR PRIMARY KEY,          -- 'doh_hdx', 'doh_eb', 'noah', ...
    title            VARCHAR NOT NULL,
    link             VARCHAR,
    description      VARCHAR,
    coverage_start   DATE,
    coverage_end     DATE,
    last_ingested_at TIMESTAMP,
    row_count        BIGINT
);

-- Human-readable descriptions returned by GET /schema/{table}
CREATE TABLE IF NOT EXISTS table_descriptions (
    table_name  VARCHAR NOT NULL,
    column_name VARCHAR NOT NULL,                  -- '*' for table-level description
    description VARCHAR NOT NULL,
    PRIMARY KEY (table_name, column_name)
);

-- ---------------------------------------------------------------------
-- 5. Indexes and views
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_cases_disease_week ON cases_weekly (disease, year, mw);
CREATE INDEX IF NOT EXISTS idx_rain_date          ON rainfall_daily (date);

-- Weekly rainfall totals aligned to morbidity weeks (Sunday-Saturday).
-- days_with_data < 7 means the week is partial or has missing days: filter on it.
CREATE OR REPLACE VIEW rainfall_weekly AS
SELECT r.pcode, w.year, w.mw, w.week_start,
       SUM(r.rain_mm)         AS rain_mm_total,
       COUNT(r.rain_mm)       AS days_with_data,
       BOOL_OR(r.is_forecast) AS includes_forecast
FROM rainfall_daily r
JOIN morbidity_weeks w ON r.date BETWEEN w.week_start AND w.week_end
GROUP BY r.pcode, w.year, w.mw, w.week_start;

-- Layer 2: 5-year dengue baseline per municipality per morbidity week
CREATE OR REPLACE VIEW dengue_baseline_5yr AS
SELECT c.pcode, c.mw,
       AVG(c.cases) AS mean_cases,
       MEDIAN(c.cases) AS median_cases,
       MAX(c.cases) AS max_cases
FROM cases_weekly c
WHERE c.disease = 'dengue'
  AND c.year BETWEEN (SELECT MAX(year) FROM cases_weekly) - 5
                 AND (SELECT MAX(year) FROM cases_weekly) - 1
GROUP BY c.pcode, c.mw;
