from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    title: str = "Transport delay predictor"
    version: str = "1.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8001
    model_dir: str = "ml/artifacts"


class Settings(BaseSettings):
    app: AppSettings = AppSettings()
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
