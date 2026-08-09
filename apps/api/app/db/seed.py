"""Demo data loader: `python -m app.db.seed`.

Idempotent — safe to re-run against a live database, because `make seed` is
something an engineer runs reflexively when a local stack looks odd. Seeding
never deletes: it inserts what is missing and leaves the rest alone.

Two tenants exist specifically so the cross-tenant authorisation tests have a
second tenant to be denied access to. A single-tenant seed makes those tests
vacuously pass.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, get_sessionmaker
from app.models import Document, ExtractedField, Tenant, ValidationResult
from app.services.audit import AuditService
from app.services.storage import build_storage
from securedox_shared import (
    AuditAction,
    DocumentStatus,
    DocumentType,
    Severity,
    ValidationStatus,
)

logger = get_logger(__name__)

TENANTS: tuple[tuple[str, str], ...] = (
    ("acme-lending", "Acme Lending"),
    # The control group: fixtures upload here so an acme-lending token being
    # able to read it is an unambiguous test failure.
    ("northwind-health", "Northwind Health"),
)

#: Which document types each tenant is expected to send — used by the fixture
#: generator in `fixtures/documents` to produce a realistic mix.
TENANT_DOCUMENT_MIX: dict[str, tuple[DocumentType, ...]] = {
    "acme-lending": (DocumentType.LOAN, DocumentType.ONBOARDING),
    "northwind-health": (DocumentType.MEDICAL, DocumentType.INSURANCE),
}

DEMO_DOCUMENT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
DEMO_CONTENT = b"%PDF-1.4\n% SecureDox seeded demo document\n"


async def seed() -> None:
    settings = get_settings()
    storage = build_storage(settings.storage_backend, settings.storage_local_path)

    async with get_sessionmaker()() as session:
        existing = set((await session.execute(select(Tenant.id))).scalars().all())

        created = 0
        for tenant_id, name in TENANTS:
            if tenant_id in existing:
                continue
            session.add(Tenant(id=tenant_id, name=name))
            created += 1

        storage_key = f"acme-lending/seed/{DEMO_DOCUMENT_ID}.pdf"
        await storage.put(storage_key, DEMO_CONTENT)

        demo_doc = await session.get(Document, DEMO_DOCUMENT_ID)
        documents_created = 0
        if demo_doc is None:
            demo_doc = Document(
                id=DEMO_DOCUMENT_ID,
                tenant_id="acme-lending",
                document_type=DocumentType.LOAN,
                status=DocumentStatus.VALIDATED,
                original_filename="seeded-loan-application.pdf",
                mime_type="application/pdf",
                size_bytes=len(DEMO_CONTENT),
                checksum_sha256=hashlib.sha256(DEMO_CONTENT).hexdigest(),
                storage_key=storage_key,
                correlation_id="seeded-demo-document",
                page_count=1,
                ocr_provider="mock",
                processed_at=datetime.now(UTC),
            )
            session.add(demo_doc)
            session.add_all(
                [
                    ExtractedField(
                        document_id=DEMO_DOCUMENT_ID,
                        field_name="applicant_name",
                        value="Jordan Rivera",
                        confidence=0.96,
                    ),
                    ExtractedField(
                        document_id=DEMO_DOCUMENT_ID,
                        field_name="ssn",
                        value="000-00-0000",
                        confidence=0.93,
                        is_pii=True,
                    ),
                    ExtractedField(
                        document_id=DEMO_DOCUMENT_ID,
                        field_name="loan_amount",
                        value="$45,000.00",
                        confidence=0.89,
                    ),
                    ValidationResult(
                        document_id=DEMO_DOCUMENT_ID,
                        rule_id="LOAN-001",
                        field_name="applicant_name",
                        status=ValidationStatus.PASS,
                        severity=Severity.HIGH,
                        message="Applicant name is present.",
                        is_blocking=False,
                    ),
                    ValidationResult(
                        document_id=DEMO_DOCUMENT_ID,
                        rule_id="LOAN-002",
                        field_name="ssn",
                        status=ValidationStatus.PASS,
                        severity=Severity.CRITICAL,
                        message="SSN is present.",
                        is_blocking=False,
                    ),
                ]
            )
            await session.flush()
            await AuditService(session).record(
                action=AuditAction.DOCUMENT_UPLOADED,
                tenant_id="acme-lending",
                correlation_id="seeded-demo-document",
                actor="system:seed",
                document_id=DEMO_DOCUMENT_ID,
                detail={"filename": demo_doc.original_filename},
            )
            await AuditService(session).record(
                action=AuditAction.VALIDATION_COMPLETED,
                tenant_id="acme-lending",
                correlation_id="seeded-demo-document",
                actor="system:seed",
                document_id=DEMO_DOCUMENT_ID,
                detail={"status": DocumentStatus.VALIDATED.value},
            )
            documents_created = 1

        await session.commit()
        logger.info(
            "seed_complete",
            tenants_created=created,
            tenants_total=len(TENANTS),
            documents_created=documents_created,
        )


def main() -> None:
    configure_logging(fmt="console", service="securedox-seed")

    async def _run() -> None:
        try:
            await seed()
        finally:
            await dispose_engine()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
