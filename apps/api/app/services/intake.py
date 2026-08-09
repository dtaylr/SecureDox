"""Upload orchestration — the intake gate.

The highest-risk path in the application: it is where untrusted bytes enter a
regulated system. The gate runs before anything is persisted or queued, and the
order of its checks is deliberate, cheapest-and-most-decisive first:

1. **Size** — bounded before the body is buffered, so an oversized upload
   cannot exhaust memory just to be rejected.
2. **Declared MIME** — against the tenant's allow-list.
3. **Magic bytes** — against the *declared* type. A PDF header on a file called
   `x.png` is a content-type spoof, and trusting `Content-Type` alone is how a
   polyglot payload reaches the OCR engine.
4. **Checksum / dedupe** — cheap once the bytes are in hand, and it short-circuits
   reprocessing.

Only then is the object stored, the row written and the job queued — in that
order, so a crash mid-flight can leave an orphaned blob (harmless, reaped) but
never a queued job pointing at bytes that were never stored.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    DuplicateDocumentError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.core.security import checksum
from app.models import Document
from app.services.audit import AuditService
from app.services.documents import DocumentRepository
from app.services.queue import JobQueue, build_job
from app.services.storage import StorageBackend, build_storage_key
from securedox_observability import metrics
from securedox_shared import AuditAction, DocumentStatus, DocumentType

#: Leading bytes that must be present for a declared MIME type to be believed.
#: A tuple of alternatives per type; JPEG and TIFF both have several legal starts.
_MAGIC_BYTES: Final[dict[str, tuple[bytes, ...]]] = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/tiff": (b"II*\x00", b"MM\x00*"),
}

#: Filenames are echoed back to a UI, so they are sanitised rather than trusted.
_FILENAME_MAX: Final = 255


@dataclass(frozen=True, slots=True)
class UploadRequest:
    tenant_id: str
    document_type: DocumentType
    filename: str
    mime_type: str
    content: bytes
    correlation_id: str
    actor: str


@dataclass(frozen=True, slots=True)
class UploadOutcome:
    document: Document
    duplicate_of: uuid.UUID | None = None


def sanitize_filename(raw: str) -> str:
    """Strip path components and control characters from a client filename.

    `../../etc/passwd` and a name containing a newline are both routine in
    fuzzing, and this value reaches log lines and a UI.
    """
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(ch for ch in name if ch.isprintable() and ch not in '<>:"|?*')
    return (cleaned.strip() or "unnamed")[:_FILENAME_MAX]


def _looks_like(mime_type: str, content: bytes) -> bool:
    """True when the bytes carry a signature consistent with `mime_type`.

    An unknown MIME type never reaches here — the allow-list runs first — so a
    missing entry means the allow-list and this table have drifted, which the
    startup check in `tests/api` catches.
    """
    signatures = _MAGIC_BYTES.get(mime_type)
    if signatures is None:
        return False
    return any(content.startswith(sig) for sig in signatures)


class IntakeService:
    """Accepts an upload and hands it to the worker."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: StorageBackend,
        queue: JobQueue,
        allowed_mime_types: list[str],
        max_upload_bytes: int,
    ) -> None:
        self._session = session
        self._storage = storage
        self._queue = queue
        self._allowed = frozenset(allowed_mime_types)
        self._max_bytes = max_upload_bytes
        self._repo = DocumentRepository(session)
        self._audit = AuditService(session)

    @property
    def max_upload_bytes(self) -> int:
        """Exposed so the route can bound its read before buffering the body."""
        return self._max_bytes

    async def accept(self, request: UploadRequest) -> UploadOutcome:
        digest = self._run_gate(request)

        existing = await self._repo.find_by_checksum(digest, tenant_id=request.tenant_id)
        if existing is not None:
            # Not an error the user can act on differently, but the client must
            # be able to tell "already have it" from "accepted".
            metrics.documents_rejected_at_gate_total.labels(
                tenant_id=request.tenant_id, reason="duplicate"
            ).inc()
            metrics.upload_rejections_total.labels(
                tenant_id=request.tenant_id, reason="duplicate"
            ).inc()
            raise DuplicateDocumentError(f"This document was already uploaded as {existing.id}.")

        document_id = uuid.uuid4()
        storage_key = build_storage_key(request.tenant_id, document_id, request.mime_type)

        # Bytes first: a row referencing an object that does not exist would
        # send the worker into a retry loop it can never win.
        await self._storage.put(storage_key, request.content)

        document = Document(
            id=document_id,
            tenant_id=request.tenant_id,
            document_type=request.document_type,
            status=DocumentStatus.RECEIVED,
            original_filename=sanitize_filename(request.filename),
            mime_type=request.mime_type,
            size_bytes=len(request.content),
            checksum_sha256=digest,
            storage_key=storage_key,
            correlation_id=request.correlation_id,
        )
        self._session.add(document)
        await self._session.flush()

        await self._audit.record(
            action=AuditAction.DOCUMENT_UPLOADED,
            tenant_id=request.tenant_id,
            correlation_id=request.correlation_id,
            actor=request.actor,
            document_id=document.id,
            detail={
                "filename": document.original_filename,
                "mime_type": document.mime_type,
                "size_bytes": document.size_bytes,
            },
        )

        await self._enqueue(document)

        metrics.documents_received_total.labels(
            tenant_id=request.tenant_id, document_type=request.document_type.value
        ).inc()
        return UploadOutcome(document=document)

    def _run_gate(self, request: UploadRequest) -> str:
        """Apply the intake gate, returning the checksum when it passes."""
        if len(request.content) > self._max_bytes:
            self._count_rejection(request.tenant_id, "too_large")
            raise PayloadTooLargeError(
                f"The file is {len(request.content)} bytes; the limit is {self._max_bytes}."
            )

        if not request.content:
            self._count_rejection(request.tenant_id, "empty")
            raise UnsupportedMediaTypeError("The uploaded file is empty.")

        if request.mime_type not in self._allowed:
            self._count_rejection(request.tenant_id, "mime_not_allowed")
            raise UnsupportedMediaTypeError(
                f"{request.mime_type} is not an accepted document type."
            )

        if not _looks_like(request.mime_type, request.content):
            # Reported as a media-type error, not a security alert: telling a
            # prober that its spoof was *detected* is free reconnaissance.
            self._count_rejection(request.tenant_id, "content_mismatch")
            raise UnsupportedMediaTypeError("The file contents do not match the declared type.")

        return checksum(request.content)

    def _count_rejection(self, tenant_id: str, reason: str) -> None:
        metrics.documents_rejected_at_gate_total.labels(tenant_id=tenant_id, reason=reason).inc()
        metrics.upload_rejections_total.labels(tenant_id=tenant_id, reason=reason).inc()

    async def _enqueue(self, document: Document) -> None:
        """Publish the job and advance the status to QUEUED.

        If the queue is down the QueueError propagates, the request transaction
        rolls back, and the document never existed — better than a RECEIVED row
        no worker will ever pick up.
        """
        job = build_job(
            document_id=document.id,
            tenant_id=document.tenant_id,
            document_type=document.document_type,
            storage_key=document.storage_key,
            mime_type=document.mime_type,
            checksum_sha256=document.checksum_sha256,
            correlation_id=document.correlation_id,
        )
        await self._queue.enqueue(job)

        document.status = DocumentStatus.QUEUED
        metrics.document_status_transitions_total.labels(
            from_status=DocumentStatus.RECEIVED.value, to_status=DocumentStatus.QUEUED.value
        ).inc()

        await self._audit.record(
            action=AuditAction.DOCUMENT_QUEUED,
            tenant_id=document.tenant_id,
            correlation_id=document.correlation_id,
            document_id=document.id,
            detail={"storage_key": document.storage_key},
        )
