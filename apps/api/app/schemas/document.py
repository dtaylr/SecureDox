"""Document request/response models — the published API surface.

These classes generate `packages/contracts/openapi/securedox.v1.yaml`, which in
turn generates the TypeScript client types. A change here propagates to the web
app, the mobile app and the Pact contracts, so treat every field as versioned.

PII masking happens at *this* layer, not in the ORM: the worker legitimately
needs the raw SSN to validate it, while no HTTP response ever should.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from securedox_shared import (
    PII_FIELDS,
    DocumentStatus,
    DocumentType,
    FieldSource,
    Severity,
    ValidationStatus,
)

MASK = "••••"


class DocumentUploadResponse(BaseModel):
    """Returned by POST /documents — a 202, not a 201.

    The document exists, but nothing has been extracted yet. Clients poll
    `GET /documents/{id}` or watch the status stream.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    status: DocumentStatus
    document_type: DocumentType
    correlation_id: str
    #: Set when the upload matched an existing checksum: the caller gets the
    #: original document's id back with a 409 rather than a silent duplicate.
    duplicate_of: uuid.UUID | None = None


class ExtractedFieldOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    field_name: str
    value: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    source: FieldSource
    is_pii: bool
    was_corrected: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_value(self) -> str | None:
        """What a UI may render. PII is masked here and only here."""
        if self.value is None:
            return None
        return MASK if self.is_pii else self.value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def low_confidence(self) -> bool:
        """Flags a field a human should re-read even though it passed.

        The threshold is the reliability signal this platform is built to
        surface: rules can pass on a confidently-wrong extraction.
        """
        return self.confidence < 0.80


class ValidationResultOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    rule_id: str
    field_name: str
    status: ValidationStatus
    severity: Severity
    message: str
    is_blocking: bool


class DocumentSummary(BaseModel):
    """List-view projection. Deliberately excludes extracted content."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    document_type: DocumentType
    status: DocumentStatus
    original_filename: str
    size_bytes: int
    created_at: datetime
    processed_at: datetime | None = None


class DocumentDetail(DocumentSummary):
    """Single-document view, including fields and every rule outcome."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    mime_type: str
    checksum_sha256: str
    correlation_id: str
    page_count: int | None = None
    ocr_provider: str | None = None
    rejection_reason: str | None = None
    extracted_fields: list[ExtractedFieldOut] = Field(default_factory=list)
    validation_results: list[ValidationResultOut] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def blocking_failures(self) -> list[str]:
        """Rule ids that caused a rejection — the "why" a reviewer needs first."""
        return [r.rule_id for r in self.validation_results if r.is_blocking]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def needs_manual_review(self) -> bool:
        return self.status == DocumentStatus.REVIEW_REQUIRED or any(
            field.low_confidence for field in self.extracted_fields
        )


class FieldCorrection(BaseModel):
    """A human overriding an OCR value.

    Correcting a PII field is allowed; echoing it back is not, so the response
    re-serialises through `ExtractedFieldOut` and comes back masked.
    """

    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=3, max_length=500)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def touches_pii(self) -> bool:
        return self.field_name in PII_FIELDS


class DocumentSubmitRequest(BaseModel):
    """Reviewer attestation before the document leaves intake."""

    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class DocumentReviewRequest(BaseModel):
    """Reviewer edits made before final submission."""

    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=3, max_length=500)
    corrections: list[FieldCorrection] = Field(default_factory=list, max_length=25)


class DocumentReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    status: DocumentStatus
    needs_manual_review: bool
    corrections_applied: int


class DocumentSubmitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    status: DocumentStatus
    submitted: bool = True
    audit_event_id: uuid.UUID


class DocumentListQuery(BaseModel):
    """Validated query parameters for the list endpoint."""

    model_config = ConfigDict(extra="forbid")

    status: DocumentStatus | None = None
    document_type: DocumentType | None = None
    cursor: str | None = None
    #: Capped so a client cannot ask for the whole tenant in one page.
    limit: int = Field(default=25, ge=1, le=100)
