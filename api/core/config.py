from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
GIS_DIR = BASE_DIR / "data" / "gis"
EPI_DIR = BASE_DIR / "data" / "epidemiology"

def gis(name: str) -> str:
    return (GIS_DIR / name).as_posix()
def epi(name: str) -> str:
    return (EPI_DIR / name).as_posix()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "EpiFlood API"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    db_path: str = str(Path(__file__).resolve().parents[1] / "db" / "database.duckdb")
    cors_origins: list[str] = ["http://localhost:5173"]
    allowed_hosts: list[str] = ["*"]

settings = Settings()
