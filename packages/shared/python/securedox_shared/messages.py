"""Queue message contract between the API (producer) and the worker (consumer).

This is a versioned contract exactly like the OpenAPI spec. `tests/contract`
validates real enqueued payloads against
`packages/contracts/json-schema/intake-job.v1.schema.json`, which is generated
from this model — so the two can never silently drift.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .enums import DocumentType

SCHEMA_VERSION = 1


class IntakeJob(BaseModel):
    """Payload enqueued when a document is accepted for processing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    document_id: UUID
    tenant_id: str = Field(min_length=1, max_length=64)
    document_type: DocumentType
    storage_key: str = Field(min_length=1, max_length=512)
    mime_type: str
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    correlation_id: str = Field(min_length=8, max_length=64)
    enqueued_at: datetime
    attempt: int = Field(default=1, ge=1, le=10)


class ExtractionResult(BaseModel):
    """What the OCR adapter hands back, independent of vendor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: UUID
    provider: str
    fields: dict[str, str | None]
    confidences: dict[str, float]
    page_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    #: Set when the adapter itself is unsure — drives the false-confidence check.
    degraded: bool = False
