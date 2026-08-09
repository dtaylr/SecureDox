"""Audit log response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from securedox_shared import AuditAction


class AuditEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID | None
    action: AuditAction
    actor: str
    correlation_id: str
    detail: dict[str, Any]
    created_at: datetime
