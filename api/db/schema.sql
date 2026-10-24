-- =====================================================================
-- EpiFlood API: DuckDB schema
-- Laguna disease surveillance, rainfall, and flood-risk analysis
--
-- Defined here: the tables below.
-- Created by the ingestion pipeline (build_map_tables.py), NOT here:
--   health_units, flood_hazards, barangays, pcode_lookup (view),
--   bgy_dengue_clusters, bgy_lepto_clusters, bgy_rainfall
-- There is no cases_weekly table: municipality-level case counts are not used.
-- =====================================================================
 
-- 1. Administrative reference data
 
CREATE TABLE IF NOT EXISTS municipalities (
    pcode            VARCHAR PRIMARY KEY,
    name             VARCHAR NOT NULL,
    type             VARCHAR NOT NULL CHECK (type IN ('city', 'municipality')),
    province         VARCHAR NOT NULL DEFAULT 'Laguna',
    region           VARCHAR NOT NULL DEFAULT 'Region IV-A',
    centroid_lng     DOUBLE,
    centroid_lat     DOUBLE,
    area_km2         DOUBLE,
    boundary_geojson VARCHAR
);
 
CREATE TABLE IF NOT EXISTS morbidity_weeks (
    year       INTEGER NOT NULL,
    mw         INTEGER NOT NULL CHECK (mw BETWEEN 1 AND 53),
    week_start DATE NOT NULL,
    week_end   DATE NOT NULL,
    PRIMARY KEY (year, mw)
);
 
-- 2. Province-level weekly cases (DOH-Epi HDX file, 2016-2021)
 
CREATE TABLE IF NOT EXISTS dengue_cases_laguna_weekly (
    date     DATE,
    cases    INTEGER,
    deaths   INTEGER,
    PRIMARY KEY (date)
);
 
-- 3. Weekly rainfall per municipality
 
CREATE TABLE IF NOT EXISTS rainfall_per_muni_weekly (
    municipality_pcode          VARCHAR NOT NULL,
    date           DATE,
    precipitation_mm  DOUBLE,
    PRIMARY KEY (municipality_pcode, date)
);
 

CREATE TABLE IF NOT EXISTS rainfall_laguna_weekly (
    date           DATE,
    precipitation_mm  DOUBLE,
    PRIMARY KEY (date)
);

-- 4. Flood hazard summaries (pct of unit area per NOAH level)
 
CREATE TABLE IF NOT EXISTS hazard_by_municipality (
    municipality_pcode VARCHAR NOT NULL,
    hazard_level INTEGER NOT NULL,
    area_km2 DOUBLE NOT NULL,
    pct_of_area DOUBLE NOT NULL,
    PRIMARY KEY (municipality_pcode, hazard_level)
);

CREATE TABLE IF NOT EXISTS hazard_by_barangay (
    adm4_pcode VARCHAR PRIMARY KEY,
    pct_flood_hazard_2 DOUBLE NOT NULL,
    pct_flood_hazard_3 DOUBLE NOT NULL
);

-- 5. Source inventory and table documentation
 
CREATE TABLE IF NOT EXISTS data_sources (
    source_id        VARCHAR PRIMARY KEY,
    title            VARCHAR NOT NULL,
    link             VARCHAR,
    description      VARCHAR,
    coverage_start   DATE,
    coverage_end     DATE,
    last_ingested_at TIMESTAMP,
    row_count        BIGINT
);
 
CREATE TABLE IF NOT EXISTS table_descriptions (
    table_name  VARCHAR NOT NULL,
    column_name VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    PRIMARY KEY (table_name, column_name)
);
 
 