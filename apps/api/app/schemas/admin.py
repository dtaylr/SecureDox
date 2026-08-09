"""Admin/status dashboard response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from securedox_shared import AuditAction, DocumentStatus


class StatusCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DocumentStatus
    count: int


class RecentAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID | None
    action: AuditAction
    actor: str
    correlation_id: str
    detail: dict[str, Any]
    created_at: datetime


class AdminStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    queue_depth: int
    documents_total: int
    documents_by_status: list[StatusCount]
    recent_audit_events: list[RecentAuditEvent]
