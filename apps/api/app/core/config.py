"""Typed application settings.

Everything the API needs comes from the environment (12-factor). The defaults
here are safe for local development only — every deployed environment injects
real values through Terraform-managed secrets.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["local", "ci", "staging", "production"]
OcrProvider = Literal["mock", "tesseract", "vendor"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- core ---
    securedox_env: Environment = "local"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    service_name: str = "securedox-api"
    service_version: str = "0.1.0"

    # --- datastores ---
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://securedox:securedox_local_pw@localhost:5432/securedox"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_statement_timeout_ms: int = 5_000

    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    queue_name: str = "securedox:intake"

    # --- http ---
    api_host: str = "0.0.0.0"  # noqa: S104 — bound inside a container network
    api_port: int = 8000
    # NoDecode: pydantic-settings JSON-decodes complex fields inside the env
    # source, before any field_validator runs, so a plain comma-separated
    # value raised SettingsError instead of reaching _split_csv below.
    api_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    request_timeout_seconds: int = 30

    # --- auth ---
    auth_jwt_secret: str = "local-dev-only-not-a-real-secret"  # noqa: S105 - local default, overridden per environment
    auth_jwt_issuer: str = "securedox-local"
    auth_jwt_algorithm: str = "HS256"
    auth_token_ttl_seconds: int = 3600

    # --- storage ---
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "/var/lib/securedox/storage"
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_mime_types: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/tiff",
        ]
    )

    # --- ocr ---
    ocr_provider: OcrProvider = "mock"
    ocr_confidence_threshold: float = 0.80

    # --- observability ---
    metrics_enabled: bool = True

    @field_validator("api_cors_origins", "allowed_mime_types", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Accept both a JSON list and a plain comma-separated env string."""
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if raw.startswith("["):
            # These fields opt out of the env source's decoding, so a JSON
            # list arrives here as a string and has to be parsed explicitly.
            return json.loads(raw)
        return [item.strip() for item in raw.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.securedox_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()
