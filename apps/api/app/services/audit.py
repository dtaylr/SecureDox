"""Writing the audit trail.

Every state-changing action goes through here, and every `detail` payload is
redacted before it is written. Centralising that is the whole point: a caller
that builds its own AuditEvent can forget to redact, and the one that forgets
will be the one handling a rejection — the payload richest in PII.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent
from securedox_observability import metrics, redact
from securedox_shared import AuditAction

ACTOR_API = "system:api"
ACTOR_WORKER = "system:worker"


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        action: AuditAction,
        tenant_id: str,
        correlation_id: str,
        actor: str = ACTOR_API,
        document_id: uuid.UUID | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Append one row. Does not commit — the request transaction owns that.

        Deliberate coupling: an audit row and the change it describes commit
        together or not at all. A separately-committed audit trail can record
        events that never happened.
        """
        event = AuditEvent(
            action=action,
            tenant_id=tenant_id,
            document_id=document_id,
            actor=actor,
            correlation_id=correlation_id,
            detail=redact(detail or {}),
        )
        self._session.add(event)
        metrics.audit_events_total.labels(action=action.value).inc()
        return event
