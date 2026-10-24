"""Build Layer 0 from the cleaned NOAH flood GeoJSON.   python -m pipelines.build_hazard_layer

Input : data/gis/processed/Laguna_Flood_5year_cleaned.geojson  (~96 MB, 105,924 small polygons, props: Var, hazard_label)
Output: data/gis/processed/hazard_simplified.geojson  (detail=low)   hazard_detailed.geojson  (detail=high)

Steps per hazard level: make valid -> dissolve into one geometry -> simplify -> drop specks -> one MultiPolygon.
Prints file sizes (raw and gzipped, which is what the browser downloads). Needs requirements-pipelines.txt
(geopandas, shapely>=2). Dissolving ~100k polygons can take a few minutes.
"""

import gzip
import json
import sys
import time

import geopandas as gpd
import shapely
from shapely.geometry import MultiPolygon

from core.config import GIS_DIR

SRC = GIS_DIR / "processed" / "Laguna_Flood_5year_cleaned.geojson"
OUT = GIS_DIR / "processed"
LABELS = {1: "Low", 2: "Medium", 3: "High"}

# name: (simplify tolerance in degrees, drop parts smaller than this many square degrees)
# 0.001 deg ~ 110 m; 1e-7 sq deg ~ (35 m)^2.  Tune these until the gzipped size suits you.
VARIANTS = {
    "hazard_simplified.geojson": (0.0010, 1e-7),
    "hazard_detailed.geojson": (0.0003, 1e-8),
}


def reduce(geom, tol: float, min_area: float):
    geom = shapely.make_valid(geom).simplify(tol, preserve_topology=True)
    parts = [p for p in shapely.get_parts(geom) if p.geom_type == "Polygon" and p.area >= min_area]
    return shapely.set_precision(MultiPolygon(parts), 1e-5)       # ~1 m grid: shorter coordinate strings


def main() -> None:
    if not SRC.exists():
        sys.exit(f"Missing {SRC}")
    t = time.time()
    gdf = gpd.read_file(SRC)
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    gdf["hazard_level"] = gdf["Var"].astype(int)
    print(f"read {len(gdf):,} polygons in {time.time() - t:.0f}s")

    dissolved = {lvl: shapely.union_all(g.geometry.values) for lvl, g in gdf.groupby("hazard_level")}
    print(f"dissolved {len(dissolved)} levels in {time.time() - t:.0f}s")

    for name, (tol, min_area) in VARIANTS.items():
        features = []
        for lvl, geom in sorted(dissolved.items()):
            m = reduce(geom, tol, min_area)
            features.append({"type": "Feature", "properties": {"hazard_level": lvl, "label": LABELS.get(lvl)},
                             "geometry": json.loads(shapely.to_geojson(m))})
        text = json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"))
        (OUT / name).write_text(text, encoding="utf-8")
        parts = sum(len(f["geometry"]["coordinates"]) for f in features)
        print(f"{name}: {len(text) / 1e6:.1f} MB raw, {len(gzip.compress(text.encode(), 6)) / 1e6:.1f} MB gzipped, {parts:,} polygons")


if __name__ == "__main__":
    main()