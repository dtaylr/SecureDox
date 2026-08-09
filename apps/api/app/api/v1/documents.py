"""Document endpoints.

Every handler here is thin: parse, delegate to a service, serialise. The tenant
comes from `principal.tenant_id` in all four routes — grep for `tenant_id=` in
this file and you should see the same source every time.

`principal` is the *first* parameter of every protected handler, deliberately.
FastAPI resolves dependencies in declaration order, so authentication runs
before the database session is opened; declared the other way round, an
unauthenticated flood would take a connection from the pool per request before
being rejected. Keep it first.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status

from app.api.deps import (
    CorrelationDep,
    IntakeDep,
    PrincipalDep,
    SessionDep,
    StorageDep,
    require_roles,
)
from app.core.errors import (
    InvalidStateTransitionError,
    NotFoundError,
    PayloadTooLargeError,
    ValidationError,
)
from app.core.security import ROLE_ADMIN, ROLE_REVIEWER, ROLE_UPLOADER, Principal
from app.models import ExtractedField
from app.schemas.common import Page, PageMeta
from app.schemas.document import (
    DocumentDetail,
    DocumentSubmitRequest,
    DocumentSubmitResponse,
    DocumentSummary,
    DocumentUploadResponse,
    ExtractedFieldOut,
    FieldCorrection,
)
from app.services.audit import AuditService
from app.services.documents import Cursor, DocumentRepository
from app.services.intake import UploadRequest
from securedox_shared import AuditAction, DocumentStatus, DocumentType, FieldSource

router = APIRouter(prefix="/documents", tags=["documents"])

#: Streamed in chunks so a lying `Content-Length` cannot buy an oversized read.
_READ_CHUNK = 64 * 1024


async def _read_bounded(upload: UploadFile, limit: int) -> bytes:
    """Buffer an upload, aborting as soon as it exceeds `limit`.

    `UploadFile.read()` with no argument would happily materialise a 2 GB body
    before anyone checks its size. Reading one chunk past the limit is enough
    to know it is too big.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_READ_CHUNK):
        total += len(chunk)
        if total > limit:
            raise PayloadTooLargeError(f"The file exceeds the {limit} byte limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for processing",
)
async def upload_document(
    principal: Annotated[Principal, require_roles(ROLE_UPLOADER, ROLE_ADMIN)],
    intake: IntakeDep,
    correlation_id: CorrelationDep,
    document_type: Annotated[DocumentType, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentUploadResponse:
    """Accept a document. 202, not 201: extraction has not happened yet."""
    content = await _read_bounded(file, intake.max_upload_bytes)

    outcome = await intake.accept(
        UploadRequest(
            tenant_id=principal.tenant_id,
            document_type=document_type,
            filename=file.filename or "unnamed",
            mime_type=file.content_type or "application/octet-stream",
            content=content,
            correlation_id=correlation_id,
            actor=principal.subject,
        )
    )
    return DocumentUploadResponse(
        id=outcome.document.id,
        status=outcome.document.status,
        document_type=outcome.document.document_type,
        correlation_id=correlation_id,
    )


@router.get("", response_model=Page[DocumentSummary], summary="List documents")
async def list_documents(
    principal: PrincipalDep,
    session: SessionDep,
    status_filter: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    document_type: Annotated[DocumentType | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[DocumentSummary]:
    """A page of this tenant's documents, newest first."""
    repo = DocumentRepository(session)
    rows, next_cursor = await repo.list_page(
        tenant_id=principal.tenant_id,
        limit=limit,
        cursor=Cursor.decode(cursor) if cursor else None,
        status=status_filter,
        document_type=document_type,
    )
    return Page[DocumentSummary](
        items=[DocumentSummary.model_validate(row) for row in rows],
        meta=PageMeta(
            next_cursor=next_cursor.encode() if next_cursor else None,
            has_more=next_cursor is not None,
            limit=limit,
        ),
    )


@router.get("/{document_id}", response_model=DocumentDetail, summary="Get one document")
async def get_document(
    principal: PrincipalDep,
    session: SessionDep,
    document_id: uuid.UUID,
) -> DocumentDetail:
    """Full detail including extracted fields — PII masked by the serialiser."""
    repo = DocumentRepository(session)
    document = await repo.get(document_id, tenant_id=principal.tenant_id)
    return DocumentDetail.model_validate(document)


@router.get(
    "/{document_id}/content",
    summary="Download the original file",
    response_class=Response,
)
async def download_document(
    principal: Annotated[Principal, require_roles(ROLE_REVIEWER, ROLE_ADMIN)],
    session: SessionDep,
    storage: StorageDep,
    document_id: uuid.UUID,
) -> Response:
    """Return the stored bytes.

    `Content-Disposition: attachment` is not decoration: serving a
    user-uploaded PDF inline lets it script against this origin.
    """
    repo = DocumentRepository(session)
    document = await repo.get(document_id, tenant_id=principal.tenant_id)
    content = await storage.get(document.storage_key)
    return Response(
        content=content,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.original_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch(
    "/{document_id}/fields",
    response_model=ExtractedFieldOut,
    summary="Correct an extracted field",
)
async def correct_field(
    principal: Annotated[Principal, require_roles(ROLE_REVIEWER, ROLE_ADMIN)],
    session: SessionDep,
    correlation_id: CorrelationDep,
    document_id: uuid.UUID,
    correction: FieldCorrection,
) -> ExtractedFieldOut:
    """Record a human override of an OCR value.

    The original is preserved in `original_value` — it is both a regulatory
    requirement and the ground-truth signal for the accuracy reporting that
    makes the OCR adapter's real error rate measurable.
    """
    repo = DocumentRepository(session)
    document = await repo.get(document_id, tenant_id=principal.tenant_id)

    field = next(
        (f for f in document.extracted_fields if f.field_name == correction.field_name),
        None,
    )
    if field is None:
        raise NotFoundError(f"No extracted field named {correction.field_name!r}.")
    if document.status == DocumentStatus.QUARANTINED:
        raise ValidationError("A quarantined document cannot be edited.")

    if field.original_value is None:
        field.original_value = field.value
    field.value = correction.value
    field.source = FieldSource.MANUAL
    field.is_pii = ExtractedField.flag_pii(field.field_name)

    await AuditService(session).record(
        action=AuditAction.FIELD_CORRECTED,
        tenant_id=principal.tenant_id,
        correlation_id=correlation_id,
        actor=principal.subject,
        document_id=document.id,
        # The new value is deliberately absent: `reason` explains the change,
        # and the value itself is frequently the PII we are trying not to log.
        detail={"field_name": field.field_name, "reason": correction.reason},
    )

    out = ExtractedFieldOut.model_validate(field)
    return out.model_copy(update={"was_corrected": True})


@router.post(
    "/{document_id}/submit",
    response_model=DocumentSubmitResponse,
    summary="Submit a reviewed document",
)
async def submit_reviewed_document(
    principal: Annotated[Principal, require_roles(ROLE_REVIEWER, ROLE_ADMIN)],
    session: SessionDep,
    correlation_id: CorrelationDep,
    document_id: uuid.UUID,
    payload: DocumentSubmitRequest,
) -> DocumentSubmitResponse:
    """Record reviewer submission after OCR and validation have completed."""
    repo = DocumentRepository(session)
    document = await repo.get(document_id, tenant_id=principal.tenant_id)

    if document.status not in (DocumentStatus.VALIDATED, DocumentStatus.REJECTED):
        raise InvalidStateTransitionError(
            "Only processed documents can be submitted from review."
        )

    event = await AuditService(session).record(
        action=AuditAction.DOCUMENT_SUBMITTED,
        tenant_id=principal.tenant_id,
        correlation_id=correlation_id,
        actor=principal.subject,
        document_id=document.id,
        detail={"status": document.status.value, "note": payload.note},
    )
    await session.flush()

    return DocumentSubmitResponse(
        id=document.id,
        status=document.status,
        audit_event_id=event.id,
    )
