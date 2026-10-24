import os
from pathlib import Path
import geopandas as gpd

os.environ["OGR_GEOJSON_MAX_OBJ_SIZE"] = "0"

def test_load_hazard_geojson():
    file_path = Path(__file__).parent.parent / "data" / "gis" / "processed" / "laguna_floodhazard_5year.geojson"
    
    # Check if file exists to give a clear error if it hasn't been generated yet
    assert file_path.exists(), f"GeoJSON file not found at {file_path}. Run your ETL pipeline first!"

    gdf = gpd.read_file(file_path)
    
    print("Total Bounds:", gdf.total_bounds) 
    
    assert not gdf.empty, "The GeoDataFrame is empty."