"""Envelopes shared by every response.

Pagination is cursor-based rather than offset-based: the document list is
ordered by `created_at DESC` and grows at the head, so an offset page 2 would
silently skip rows the moment an upload lands mid-scroll. The mobile client's
infinite scroll depends on this, and `tests/mobile-api` asserts it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """One field-level or rule-level reason inside an error response."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    rule_id: str | None = None
    message: str


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="Stable machine-readable token. Clients switch on this.")
    message: str = Field(description="Human-readable text. May be reworded without notice.")
    correlation_id: str = Field(description="Quote this in a support ticket.")
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """The only error shape the API emits."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


class PageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Opaque. Clients must echo it back verbatim, never construct one.
    next_cursor: str | None = None
    has_more: bool = False
    limit: int


class Page[T](BaseModel):
    """A page of `T`, plus the cursor for the next one.

    PEP 695 syntax — the project targets 3.12, and pydantic builds the concrete
    model per parameterisation either way.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[T]
    meta: PageMeta


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Dependency-by-dependency readiness.

    Kept separate from liveness: a failed readiness probe should pull the pod
    out of the load balancer, while a failed liveness probe restarts it. A
    database blip must do the former, never the latter.
    """

    model_config = ConfigDict(extra="forbid")

    status: str
    checks: dict[str, Any]
