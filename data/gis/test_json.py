import os
os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"
import geopandas as gpd

gdf = gpd.read_file("laguna_floodhazard_5year.geojson")
print(gdf.total_bounds)   # minx, miny, maxx, maxy