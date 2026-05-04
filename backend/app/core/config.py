from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    app_name: str = "darija-ai-backend"
    app_version: str = "0.1.0"

    database_url: PostgresDsn
    database_pool_size: int = 5
    database_max_overflow: int = 10

    redis_url: RedisDsn

    anthropic_api_key: str = Field(..., min_length=10)
    replicate_api_token: SecretStr
    openai_api_key: str | None = None

    localizer_prompt_version: str = "v1"

    r2_account_id: str = ""
    r2_access_key_id: SecretStr = SecretStr("")
    r2_secret_access_key: SecretStr = SecretStr("")
    r2_bucket_name: str = "darija-ai-images"
    r2_endpoint_url: str = ""
    r2_public_url: str = ""

    sentry_dsn: str | None = None

    cors_origins: list[str] = ["http://localhost:3000"]

    admin_jwt_secret: str = Field(default="dev-only-change-me", min_length=10)
    admin_jwt_algorithm: str = "HS256"
    admin_jwt_expiry_seconds: int = 3600

    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"

    @property
    def database_url_str(self) -> str:
        return str(self.database_url)

    @property
    def redis_url_str(self) -> str:
        return str(self.redis_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
