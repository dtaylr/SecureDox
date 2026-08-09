"""Tenant-scoped audit log endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import SessionDep, require_roles
from app.core.security import ROLE_ADMIN, ROLE_REVIEWER, Principal
from app.models import AuditEvent
from app.schemas.audit import AuditEventOut
from app.schemas.common import Page, PageMeta
from securedox_shared import AuditAction

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditEventOut], summary="List tenant audit events")
async def list_audit_logs(
    principal: Annotated[Principal, require_roles(ROLE_REVIEWER, ROLE_ADMIN)],
    session: SessionDep,
    document_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[AuditAction | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[AuditEventOut]:
    """Return only audit rows visible to the caller's tenant."""
    stmt = select(AuditEvent).where(AuditEvent.tenant_id == principal.tenant_id)
    if document_id is not None:
        stmt = stmt.where(AuditEvent.document_id == document_id)
    if action is not None:
        stmt = stmt.where(AuditEvent.action == action)
    stmt = stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit)

    events = list((await session.execute(stmt)).scalars().all())
    return Page[AuditEventOut](
        items=[AuditEventOut.model_validate(event) for event in events],
        meta=PageMeta(next_cursor=None, has_more=False, limit=limit),
    )
