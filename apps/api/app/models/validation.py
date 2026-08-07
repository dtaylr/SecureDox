"""Per-rule validation outcomes.

One row per rule evaluated, pass or fail — not just failures. Storing the
passes is what makes the rule catalogue auditable: a regulator asking "was
LOAN-002 checked on this document?" gets a row, not an inference from silence.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import (
    UUID as PgUUID,  # noqa: N811 - conventional alias for the dialect type
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from securedox_shared import Severity, ValidationStatus

if TYPE_CHECKING:
    from app.models.document import Document


class ValidationResult(Base, TimestampMixin):
    __tablename__ = "validation_results"
    __table_args__ = (
        UniqueConstraint("document_id", "rule_id", name="uq_validation_results_document_rule"),
        # Powers the "top rejection reasons" dashboard panel without a scan.
        Index("ix_validation_results_rule_status", "rule_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: Matches `FieldRule.rule_id` verbatim — the join key between stored
    #: results and the shared rule catalogue.
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[ValidationStatus] = mapped_column(
        SAEnum(
            ValidationStatus,
            name="validation_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    severity: Mapped[Severity] = mapped_column(
        SAEnum(
            Severity,
            name="severity",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(String(500), nullable=False)
    #: The value that tripped the rule — NULL for PII fields, because an error
    #: message is exactly where a leaked SSN would end up.
    observed: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: True when this outcome alone is enough to reject (HIGH/CRITICAL fail).
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    document: Mapped[Document] = relationship(back_populates="validation_results")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ValidationResult {self.rule_id} {self.status}>"
