"""Worker configuration.

Separate from the API's `Settings` even though several keys overlap: the worker
is deployed independently and must be able to scale, restart and be configured
without touching the API. Sharing one settings class would silently couple them.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    securedox_env: Literal["local", "ci", "staging", "production"] = "local"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    service_name: str = "securedox-worker"
    service_version: str = "0.1.0"

    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://securedox:securedox_local_pw@localhost:5432/securedox"
    )
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    queue_name: str = "securedox:intake"

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "/var/lib/securedox/storage"

    # --- ocr ---
    ocr_provider: Literal["mock", "tesseract", "vendor"] = "mock"
    ocr_vendor_url: str = ""
    ocr_vendor_api_key: str = ""
    ocr_timeout_seconds: int = 30
    ocr_confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    #: Only the chaos suite raises this; it makes the mock adapter misread.
    ocr_degradation_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # --- concurrency and retries ---
    worker_concurrency: int = Field(default=4, ge=1, le=64)
    worker_max_retries: int = Field(default=3, ge=0, le=10)
    worker_job_timeout_seconds: int = Field(default=120, ge=1)
    #: Blocking pop timeout. Bounded so a shutdown signal is noticed promptly
    #: instead of after a job finally arrives.
    poll_timeout_seconds: int = Field(default=5, ge=1, le=60)

    metrics_enabled: bool = True
    metrics_port: int = 9100

    @property
    def dead_letter_queue(self) -> str:
        return f"{self.queue_name}:dead"


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
