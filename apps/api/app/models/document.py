"""Document — the aggregate root of the intake pipeline.

Status is the contract between the API and the worker. The legal transitions
live in `securedox_shared.ALLOWED_TRANSITIONS`, are applied by both services,
and are asserted against real rows by `tests/db/suites/test_state_machine.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from securedox_shared import DocumentStatus, DocumentType, can_transition

if TYPE_CHECKING:
    from app.models.extraction import ExtractedField
    from app.models.validation import ValidationResult


def _pg_enum(enum_cls: type, name: str) -> SAEnum:
    """Store enums by *value*, not by Python member name.

    `values_callable` matters: without it SQLAlchemy persists the member name,
    which silently diverges from the string the OpenAPI schema publishes.
    """
    return SAEnum(
        enum_cls, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e]
    )


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        # Same bytes uploaded twice by one tenant is a duplicate, not a new
        # document. Scoped to the tenant so two tenants may hold the same file.
        UniqueConstraint("tenant_id", "checksum_sha256", name="uq_documents_tenant_checksum"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("page_count IS NULL OR page_count >= 0", name="page_count_non_negative"),
        # The list view is always "this tenant, newest first, optionally by
        # status" — this index serves all three shapes.
        Index("ix_documents_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("ix_documents_correlation_id", "correlation_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    document_type: Mapped[DocumentType] = mapped_column(
        _pg_enum(DocumentType, "document_type"), nullable=False
    )
    status: Mapped[DocumentStatus] = mapped_column(
        _pg_enum(DocumentStatus, "document_status"),
        nullable=False,
        default=DocumentStatus.RECEIVED,
    )

    # --- file identity ---
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    #: Content address. Also the dedupe key and the integrity check the worker
    #: re-runs after download, so a corrupted object store cannot go unnoticed.
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)

    # --- pipeline metadata ---
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    ocr_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)

    #: Populated on REJECTED/FAILED/QUARANTINED. Safe to show a user: it is
    #: built from rule messages, never from raw extracted content.
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    extracted_fields: Mapped[list[ExtractedField]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="selectin"
    )
    validation_results: Mapped[list[ValidationResult]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    def can_move_to(self, target: DocumentStatus) -> bool:
        return can_transition(self.status, target)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Document {self.id} {self.tenant_id} {self.status}>"
