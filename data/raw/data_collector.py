import requests
import pandas as pd
import geopandas as gpd

gdf = gpd.read_file("gis/phl_admin3.geojson")
if gdf.crs != "EPSG:4326":
    gdf = gdf.to_crs("EPSG:4326")


# Step 1: Get Laguna GeoData
print("Loading GeoJSON...")
print(gdf.columns)
laguna_gdf = gdf[gdf["adm2_name"] == "Laguna"].copy()
print(laguna_gdf[["adm3_pcode", "adm3_name", "center_lat", "center_lon", "area_sqkm",  "geometry"]].head())
print(f"Found {len(laguna_gdf)} municipalities in Laguna.")

laguna_gdf.to_file("gis/laguna_geodata.geojson", driver="GeoJSON")

# Step 2: Fetch Laguna Rainfall Data (mm)

url = "https://archive-api.open-meteo.com/v1/archive"
all_municipality_weekly_data = []
for index, row in laguna_gdf.iterrows():
    pcode = row["adm3_pcode"]
    name = row[ "adm3_name"]
    lat = row["center_lat"]
    lon = row["center_lon"]
    print(f"Fetching data for: {name} (Lat: {lat}, Lon: {lon})")
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2021-01-01",
        "end_date": "2026-10-16",
        "hourly": "precipitation",
        "timezone": "auto"
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        df_muni = pd.DataFrame({
            "date": data["hourly"]["date"],
            "precipitation_mm": data["hourly"]["precipitation"]
        })
        
        df_muni["date"] = pd.to_datetime(df_muni["date"])
        df_muni = df_muni.set_index("date")
        
        df_weekly = df_muni.resample("W-MON")["precipitation_mm"].sum().reset_index()
        
        df_weekly["municipality"] = pcode
        
        all_municipality_weekly_data.append(df_weekly)
        
    except Exception as e:
        print(f"Error fetching data for {name}: {e}")

if all_municipality_weekly_data:
    master_df = pd.concat(all_municipality_weekly_data, ignore_index=True)
    
    # Reorder columns to look clean
    master_df = master_df[["municipality", "date", "precipitation_mm"]]
    
    print("\n--- Combined Weekly Rainfall Data Preview ---")
    print(master_df.head(10))
    
    # 4. Save to CSV
    output_path = "gis/laguna_weekly_rainfall_2021_2025.csv"
    master_df.to_csv(output_path, index=False)
    print(f"\nSuccessfully saved all data to {output_path}!")
else:
    print("No data was collected.")
