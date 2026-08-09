"""Tenant-scoped admin/status views."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import desc, func, select

from app.api.deps import QueueDep, SessionDep, require_roles
from app.core.security import ROLE_ADMIN, Principal
from app.models import AuditEvent, Document
from app.schemas.admin import AdminStatusResponse, RecentAuditEvent, StatusCount
from securedox_shared import DocumentStatus

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status", response_model=AdminStatusResponse, summary="Admin status dashboard")
async def status_dashboard(
    principal: Annotated[Principal, require_roles(ROLE_ADMIN)],
    session: SessionDep,
    queue: QueueDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> AdminStatusResponse:
    counts_stmt = (
        select(Document.status, func.count(Document.id))
        .where(Document.tenant_id == principal.tenant_id)
        .group_by(Document.status)
    )
    count_rows = (await session.execute(counts_stmt)).all()
    count_map = {status: int(count) for status, count in count_rows}

    audit_stmt = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == principal.tenant_id)
        .order_by(desc(AuditEvent.created_at))
        .limit(limit)
    )
    audit_rows = list((await session.execute(audit_stmt)).scalars().all())

    return AdminStatusResponse(
        tenant_id=principal.tenant_id,
        queue_depth=await queue.depth(),
        documents_total=sum(count_map.values()),
        documents_by_status=[
            StatusCount(status=status, count=count_map.get(status, 0)) for status in DocumentStatus
        ],
        recent_audit_events=[RecentAuditEvent.model_validate(row) for row in audit_rows],
    )
