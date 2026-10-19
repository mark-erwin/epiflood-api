from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "EpiFlood API"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    db_path: str = "data/epiflood.duckdb"
    cors_origins: list[str] = ["http://localhost:5173"]
    allowed_hosts: list[str] = ["*"]

settings = Settings()
