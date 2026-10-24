"""Load Laguna administrative boundaries into the `municipalities` table.

Replaces: load_laguna_admin_geodata, generate_pcode_names.
"""

import json
import logging
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd

from pipeline.common import (
    ADMIN3_PATH, ADMIN4_PATH, EXPECTED_LAGUNA_LGUS, GIS_OUT, LAGUNA_ADM3_PATH, LAGUNA_ADM4_PATH, PROVINCE, REGION, TARGET_CRS, connect, init_schema,
)

log = logging.getLogger("pipelines")

LEVELS = {
    "adm3": {
        "required": ["adm3_name", "adm3_pcode", "geometry"],
        "term": "municipality",
    },
    "adm4": {
        "required": ["adm4_name", "adm4_pcode", "adm3_name", "adm3_pcode", "geometry"],
        "term": "barangay",
    },
}
OPTIONAL_GEO_COLS = ["area_sqkm", "center_lat", "center_lon"]


def load_laguna_admin(
    admin_path: Path,
    level: str = "adm3",
    out_path: Path | None = None,
    province: str = PROVINCE,
    already_filtered: bool = False,
) -> gpd.GeoDataFrame:
    """Read a PH admin GeoJSON, keep one province, return it in EPSG:4326.

    `already_filtered=True` is for files that only contain Laguna (they have no adm2_name
    column, e.g. laguna_municipality_geodata.geojson). `out_path` is honoured; None = do not write.
    """
    if level not in LEVELS:
        raise ValueError(f"level must be one of {sorted(LEVELS)}, got '{level}'")

    gdf = gpd.read_file(admin_path)
    if gdf.crs is None:
        raise ValueError(f"{admin_path} has no CRS defined")
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    needed = LEVELS[level]["required"] + ([] if already_filtered else ["adm2_name"])
    missing = [c for c in needed if c not in gdf.columns]
    if missing:
        raise ValueError(f"{admin_path} is missing columns {missing}. Found: {list(gdf.columns)}")

    if not already_filtered:
        keep = gdf["adm2_name"].astype(str).str.strip().str.upper() == province.upper()
        gdf = gdf[keep].copy()
        if gdf.empty:
            raise ValueError(f"No rows with adm2_name == '{province}' in {admin_path}")

    gdf = _fill_geo_columns(gdf)
    cols = [c for c in LEVELS[level]["required"] if c != "geometry"] + OPTIONAL_GEO_COLS + ["geometry"]
    if level == "adm4":
        cols = list(dict.fromkeys(cols))
    gdf = gdf[cols].reset_index(drop=True)

    log.info("Found %d %s(s) in %s", len(gdf), LEVELS[level]["term"], province)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(out_path, driver="GeoJSON")
    return gdf


def _fill_geo_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Use area/centroid columns from the file when present, otherwise compute them
    in a projected CRS (never in degrees)."""
    utm = gdf.to_crs(TARGET_CRS)
    if "area_sqkm" not in gdf.columns or gdf["area_sqkm"].isna().any():
        gdf["area_sqkm"] = utm.area / 1e6
    if (
        "center_lat" not in gdf.columns or "center_lon" not in gdf.columns
        or gdf[["center_lat", "center_lon"]].isna().any().any()
    ):
        centroids = utm.centroid.to_crs("EPSG:4326")
        gdf["center_lon"], gdf["center_lat"] = centroids.x, centroids.y
    return gdf


def municipality_frame(gdf: gpd.GeoDataFrame, simplify_deg: float = 0.0005) -> pd.DataFrame:
    """Shape an adm3 GeoDataFrame like the `municipalities` table."""
    names = gdf["adm3_name"].astype(str).str.strip()
    return pd.DataFrame(
        {
            "pcode": gdf["adm3_pcode"].astype(str).str.strip(),
            "name": names,
            "type": ["city" if "CITY" in n.upper() else "municipality" for n in names],
            "province": PROVINCE,
            "region": REGION,
            "centroid_lng": gdf["center_lon"].astype(float),
            "centroid_lat": gdf["center_lat"].astype(float),
            "area_km2": gdf["area_sqkm"].astype(float),
            "boundary_geojson": [
                json.dumps(g.simplify(simplify_deg, preserve_topology=True).__geo_interface__)
                for g in gdf.geometry
            ],
        }
    )


def load_municipalities(
    con: duckdb.DuckDBPyConnection,
    gdf: gpd.GeoDataFrame,
    expected_count: int | None = EXPECTED_LAGUNA_LGUS,
) -> int:
    df = municipality_frame(gdf)
    if expected_count is not None and len(df) != expected_count:
        raise ValueError(
            f"Expected {expected_count} Laguna cities/municipalities, found {len(df)}. "
            "Check the boundary file version."
        )
    if df["pcode"].duplicated().any():
        raise ValueError("Duplicate pcodes in the municipality boundary file")

    n_city = int((df["type"] == "city").sum())
    log.info("Municipalities: %d cities, %d municipalities", n_city, len(df) - n_city)

    con.register("mun_stage", df)
    con.execute(
        """
        INSERT INTO municipalities
            (pcode, name, type, province, region, centroid_lng, centroid_lat, area_km2, boundary_geojson)
        SELECT pcode, name, type, province, region, centroid_lng, centroid_lat, area_km2, boundary_geojson
        FROM mun_stage
        ON CONFLICT (pcode) DO UPDATE SET
            name = excluded.name, type = excluded.type, province = excluded.province,
            region = excluded.region, centroid_lng = excluded.centroid_lng,
            centroid_lat = excluded.centroid_lat, area_km2 = excluded.area_km2,
            boundary_geojson = excluded.boundary_geojson
        """
    )
    con.unregister("mun_stage")
    return len(df)

def pick_source(full: Path, filtered: Path) -> tuple[Path, bool] | None:
    """Prefer the national file; fall back to a pre-filtered Laguna file. None if neither exists."""
    if full.exists():
        return full, False
    if filtered.exists():
        log.info("%s not found, using the pre-filtered %s", full.name, filtered.name)
        return filtered, True
    return None


def load_adm3(out_path: Path | None = None, full: Path = ADMIN3_PATH, filtered: Path = LAGUNA_ADM3_PATH) -> gpd.GeoDataFrame:
    src = pick_source(full, filtered)
    if src is None:
        raise FileNotFoundError(f"Municipality boundaries not found: put {full.name} (or {filtered.name}) in {full.parent}")
    return load_laguna_admin(src[0], "adm3", out_path, already_filtered=src[1])


def load_adm4(out_path: Path | None = None, full: Path = ADMIN4_PATH, filtered: Path = LAGUNA_ADM4_PATH) -> gpd.GeoDataFrame | None:
    src = pick_source(full, filtered)
    return None if src is None else load_laguna_admin(src[0], "adm4", out_path, already_filtered=src[1])


def run(con: duckdb.DuckDBPyConnection) -> None:
    load_municipalities(con, load_adm3(GIS_OUT / "laguna_municipality_geodata.geojson"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _con = connect()
    init_schema(_con)
    run(_con)