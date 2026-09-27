from functools import lru_cache

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    title: str = "Moscow Transport Predictor"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    prediction_cache_ttl: int = 600
    telemetry_max_history: int = 50
    stop_speed_threshold_kmh: float = 5.0
    ml_telemetry_window_minutes: int = 30
    max_idle_gap_s: float = 120.0
    historical_packet_delay_s: float = 300.0
    dashboard_websocket_update_interval_s: float = 2.0


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: SecretStr = SecretStr("postgres")
    database: str = "transport"

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.username}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.database}"


class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/0"


class MLSettings(BaseModel):
    url: str = "http://localhost:8001/predict"
    timeout: float = 10.0


class NDTPSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 9201


class Settings(BaseSettings):
    app: AppSettings = AppSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    ndtp: NDTPSettings = NDTPSettings()
    ml: MLSettings = MLSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
