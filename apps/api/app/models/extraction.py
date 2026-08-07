"""Extracted field values and their OCR confidence.

Confidence is stored per field rather than per document because the reliability
question this platform exists to answer is field-level: "the model said it was
90% sure of an SSN and got it wrong" is the failure mode, and it is invisible
in a document-level average.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
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
from securedox_shared import PII_FIELDS, FieldSource

if TYPE_CHECKING:
    from app.models.document import Document


class ExtractedField(Base, TimestampMixin):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint("document_id", "field_name", name="uq_extracted_fields_document_field"),
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="confidence_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Nullable: "the OCR found nothing here" is a distinct, meaningful result
    #: from "the OCR found an empty string", and the rule engine treats them
    #: the same way only because `evaluate` normalises both to absent.
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    source: Mapped[FieldSource] = mapped_column(
        SAEnum(
            FieldSource,
            name="field_source",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=FieldSource.OCR,
    )

    #: Denormalised from `securedox_shared.PII_FIELDS` at write time so the API
    #: serialiser and any ad-hoc SQL can both mask without importing the rules.
    is_pii: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    #: Set when a human overrode the OCR value. Retaining the original is a
    #: regulatory requirement and the training signal for accuracy reporting.
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    document: Mapped[Document] = relationship(back_populates="extracted_fields")

    @staticmethod
    def flag_pii(field_name: str) -> bool:
        return field_name in PII_FIELDS

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        shown = "[REDACTED]" if self.is_pii else self.value
        return f"<ExtractedField {self.field_name}={shown!r} @{self.confidence:.2f}>"
