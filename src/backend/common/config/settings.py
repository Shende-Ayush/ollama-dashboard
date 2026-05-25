from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@postgres:5432/ollama_dashboard", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    default_model: str = Field(default="llama3", alias="DEFAULT_MODEL")
    max_tokens: int = Field(default=8192, alias="MAX_TOKENS")
    rate_limit_default_per_min: int = Field(default=60, alias="RATE_LIMIT_DEFAULT_PER_MIN")
    token_quota_default_daily: int = Field(default=250000, alias="TOKEN_QUOTA_DEFAULT_DAILY")
    api_key_header: str = Field(default="Authorization", alias="API_KEY_HEADER")
    ollama_container_name: str = Field(default="ollama", alias="OLLAMA_CONTAINER_NAME")
    prometheus_enabled: bool = Field(default=True, alias="PROMETHEUS_ENABLED")
    loki_enabled: bool = Field(default=True, alias="LOKI_ENABLED")
    command_guard_enabled: bool = Field(default=True, alias="COMMAND_GUARD_ENABLED")


@lru_cache
def get_settings() -> Settings:
    return Settings()
