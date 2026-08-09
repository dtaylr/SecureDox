"""Processing one document, end to end.

The pipeline: fetch bytes, verify integrity, extract, validate, persist, audit.
Each step advances the document's status, and every transition goes through
`securedox_shared.can_transition` — the worker cannot put a document into a
state the API would consider impossible.

The error handling is the substance of this module:

* **Integrity failure** → QUARANTINED, terminal, no retry. Bytes that do not
  match their checksum are either corrupt storage or tampering; reprocessing
  cannot help and re-reading them repeatedly is the wrong instinct.
* **Permanent OCR failure** → FAILED, no retry.
* **Transient OCR failure** → raised, so the consumer's retry policy sees it.
* **Anything unexpected** → FAILED with the exception type only. An exception
  string from a document parser can contain document content.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Document, ExtractedField, ValidationResult
from app.services.audit import ACTOR_WORKER, AuditService
from app.services.storage import StorageBackend
from securedox_observability import metrics
from securedox_shared import (
    AuditAction,
    DocumentStatus,
    ExtractionResult,
    IntakeJob,
    can_transition,
)
from worker.ocr import OcrAdapter, OcrError, OcrRequest
from worker.rules import RuleRunner, outcome_rows

logger = get_logger(__name__)


class IntegrityError(Exception):
    """Stored bytes do not match the checksum recorded at upload."""


@dataclass(frozen=True, slots=True)
class ProcessingOutcome:
    document_id: uuid.UUID
    status: DocumentStatus
    duration_seconds: float
    retryable: bool = False


class DocumentProcessor:
    def __init__(
        self,
        *,
        storage: StorageBackend,
        ocr: OcrAdapter,
        rules: RuleRunner,
    ) -> None:
        self._storage = storage
        self._ocr = ocr
        self._rules = rules

    async def process(self, session: AsyncSession, job: IntakeJob) -> ProcessingOutcome:
        started = time.perf_counter()
        audit = AuditService(session)

        document = await self._load(session, job)
        if document is None:
            # The row is gone but the job survived — a stale message after a
            # database restore. Dropping it is correct; retrying never helps.
            logger.warning("job_for_missing_document", document_id=str(job.document_id))
            return ProcessingOutcome(job.document_id, DocumentStatus.FAILED, 0.0)

        if document.status.is_terminal:
            # Redelivery of an already-finished job. At-least-once delivery
            # makes this routine, so it is an info, not a warning.
            logger.info(
                "job_already_terminal",
                document_id=str(document.id),
                status=document.status.value,
            )
            return ProcessingOutcome(document.id, document.status, 0.0)

        try:
            content = await self._fetch_and_verify(document)
        except IntegrityError as exc:
            await self._terminate(session, audit, document, DocumentStatus.QUARANTINED, str(exc))
            metrics.jobs_processed_total.labels(outcome="quarantined").inc()
            return ProcessingOutcome(
                document.id, DocumentStatus.QUARANTINED, time.perf_counter() - started
            )

        try:
            extraction = await self._extract(session, audit, document, content)
        except OcrError as exc:
            metrics.ocr_failures_total.labels(provider=self._ocr.name, error=exc.kind).inc()
            if not exc.permanent:
                # Surfaces to the consumer, which owns the retry budget.
                metrics.job_retries_total.labels(reason=exc.kind).inc()
                raise
            await self._terminate(session, audit, document, DocumentStatus.FAILED, str(exc))
            metrics.jobs_processed_total.labels(outcome="failed").inc()
            return ProcessingOutcome(
                document.id, DocumentStatus.FAILED, time.perf_counter() - started
            )

        verdict = await self._validate(session, audit, document, extraction)

        duration = time.perf_counter() - started
        metrics.processing_duration_seconds.labels(
            document_type=document.document_type.value
        ).observe(duration)
        outcome = {
            DocumentStatus.VALIDATED: "validated",
            DocumentStatus.REVIEW_REQUIRED: "review_required",
        }.get(verdict, "rejected")
        metrics.jobs_processed_total.labels(outcome=outcome).inc()

        return ProcessingOutcome(document.id, verdict, duration)

    # --- steps -------------------------------------------------------------

    @staticmethod
    async def _load(session: AsyncSession, job: IntakeJob) -> Document | None:
        stmt = select(Document).where(
            Document.id == job.document_id, Document.tenant_id == job.tenant_id
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _fetch_and_verify(self, document: Document) -> bytes:
        content = await self._storage.get(document.storage_key)
        digest = hashlib.sha256(content).hexdigest()
        if digest != document.checksum_sha256:
            raise IntegrityError("Stored content does not match the checksum recorded at upload.")
        return content

    async def _extract(
        self,
        session: AsyncSession,
        audit: AuditService,
        document: Document,
        content: bytes,
    ) -> ExtractionResult:
        await self._advance(session, document, DocumentStatus.EXTRACTING)
        await audit.record(
            action=AuditAction.EXTRACTION_STARTED,
            tenant_id=document.tenant_id,
            correlation_id=document.correlation_id,
            actor=ACTOR_WORKER,
            document_id=document.id,
            detail={"provider": self._ocr.name},
        )
        await session.commit()

        with metrics.observe(metrics.ocr_duration_seconds, provider=self._ocr.name):
            extraction = await self._ocr.extract(
                OcrRequest(
                    document_id=document.id,
                    document_type=document.document_type,
                    mime_type=document.mime_type,
                    content=content,
                )
            )

        document.ocr_provider = extraction.provider
        document.page_count = extraction.page_count
        self._persist_fields(session, document, extraction)

        await audit.record(
            action=AuditAction.EXTRACTION_COMPLETED,
            tenant_id=document.tenant_id,
            correlation_id=document.correlation_id,
            actor=ACTOR_WORKER,
            document_id=document.id,
            # Field *names* and confidences only — never the values.
            detail={
                "provider": extraction.provider,
                "page_count": extraction.page_count,
                "fields_found": sorted(k for k, v in extraction.fields.items() if v),
                "degraded": extraction.degraded,
            },
        )
        return extraction

    @staticmethod
    def _persist_fields(
        session: AsyncSession, document: Document, extraction: ExtractionResult
    ) -> None:
        """Replace the document's extracted fields with this extraction.

        Replace rather than append: a reprocessed document must not end up with
        two conflicting values for the same field, and the unique constraint on
        `(document_id, field_name)` would reject the insert anyway.
        """
        existing = {f.field_name: f for f in document.extracted_fields}
        for name, value in extraction.fields.items():
            confidence = extraction.confidences.get(name, 0.0)
            if (field := existing.get(name)) is not None:
                # A human correction outranks a re-extraction.
                if field.original_value is not None:
                    continue
                field.value = value
                field.confidence = confidence
            else:
                session.add(
                    ExtractedField(
                        document_id=document.id,
                        field_name=name,
                        value=value,
                        confidence=confidence,
                        is_pii=ExtractedField.flag_pii(name),
                    )
                )

    async def _validate(
        self,
        session: AsyncSession,
        audit: AuditService,
        document: Document,
        extraction: ExtractionResult,
    ) -> DocumentStatus:
        await self._advance(session, document, DocumentStatus.VALIDATING)

        verdict = self._rules.run(document.document_type, extraction)

        existing = {r.rule_id: r for r in document.validation_results}
        for row in outcome_rows(verdict):
            rule_id = str(row["rule_id"])
            if (result := existing.get(rule_id)) is not None:
                for key, value in row.items():
                    setattr(result, key, value)
            else:
                session.add(ValidationResult(document_id=document.id, **row))  # type: ignore[arg-type]

        await self._advance(session, document, verdict.status)
        document.rejection_reason = verdict.rejection_reason
        document.processed_at = datetime.now(UTC)

        await audit.record(
            action=AuditAction.VALIDATION_COMPLETED,
            tenant_id=document.tenant_id,
            correlation_id=document.correlation_id,
            actor=ACTOR_WORKER,
            document_id=document.id,
            detail={
                "status": verdict.status.value,
                "blocking_rules": [f.rule_id for f in verdict.evaluation.failures],
                "low_confidence_fields": list(verdict.low_confidence_fields),
                "needs_human_review": verdict.needs_human_review,
            },
        )
        if verdict.status == DocumentStatus.REJECTED:
            await audit.record(
                action=AuditAction.DOCUMENT_REJECTED,
                tenant_id=document.tenant_id,
                correlation_id=document.correlation_id,
                actor=ACTOR_WORKER,
                document_id=document.id,
                detail={"reason": verdict.rejection_reason},
            )

        await session.commit()
        logger.info(
            "document_processed",
            document_id=str(document.id),
            status=verdict.status.value,
            needs_human_review=verdict.needs_human_review,
        )
        return verdict.status

    # --- state helpers -----------------------------------------------------

    @staticmethod
    async def _advance(session: AsyncSession, document: Document, target: DocumentStatus) -> None:
        """Move a document forward, refusing an illegal transition.

        A refused transition is a bug in this worker, not bad input, so it
        raises rather than being logged and swallowed.
        """
        if document.status == target:
            return
        if not can_transition(document.status, target):
            raise RuntimeError(
                f"Illegal transition {document.status.value} -> {target.value} "
                f"for document {document.id}"
            )
        metrics.document_status_transitions_total.labels(
            from_status=document.status.value, to_status=target.value
        ).inc()
        document.status = target
        await session.flush()

    async def _terminate(
        self,
        session: AsyncSession,
        audit: AuditService,
        document: Document,
        status: DocumentStatus,
        reason: str,
    ) -> None:
        """Put a document into a terminal failure state and record why."""
        await self._advance(session, document, status)
        document.rejection_reason = reason[:1000]
        document.processed_at = datetime.now(UTC)

        action = (
            AuditAction.DOCUMENT_QUARANTINED
            if status == DocumentStatus.QUARANTINED
            else AuditAction.PROCESSING_FAILED
        )
        await audit.record(
            action=action,
            tenant_id=document.tenant_id,
            correlation_id=document.correlation_id,
            actor=ACTOR_WORKER,
            document_id=document.id,
            detail={"reason": reason[:500]},
        )
        await session.commit()
        logger.error(
            "document_terminated",
            document_id=str(document.id),
            status=status.value,
        )
