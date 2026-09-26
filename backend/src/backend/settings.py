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


class TCPSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 9201


class Settings(BaseSettings):
    app: AppSettings = AppSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    tcp: TCPSettings = TCPSettings()
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
