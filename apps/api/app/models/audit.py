"""Append-only audit trail.

No update or delete path exists in application code, and the migration grants
the app role INSERT/SELECT only. Retention is handled out-of-band by a
scheduled job, not by the services — an application that can delete its own
audit rows is not an audit trail.

`detail` is free-form JSON, so it is the one column most likely to leak PII;
`AuditService` runs every payload through `securedox_observability.redact`
before it is written, and `tests/security` asserts the property.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import (
    UUID as PgUUID,  # noqa: N811 - conventional alias for the dialect type
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk
from securedox_shared import AuditAction


class AuditEvent(Base):
    """One immutable row per state-changing action.

    Deliberately does not use `TimestampMixin`: there is no `updated_at`,
    because a row that can be updated is not evidence.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_events_document", "document_id"),
        Index("ix_audit_events_correlation", "correlation_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    #: No FK cascade: an audit row must survive the document it describes.
    document_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    action: Mapped[AuditAction] = mapped_column(
        SAEnum(
            AuditAction,
            name="audit_action",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )

    #: Subject that caused the event: a user id, "system:worker", or
    #: "system:api". Never an IP or an email — those are PII.
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AuditEvent {self.action} {self.document_id}>"
