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

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, get_sessionmaker
from app.models import Tenant
from securedox_shared import DocumentType

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


async def seed() -> None:
    async with get_sessionmaker()() as session:
        existing = set((await session.execute(select(Tenant.id))).scalars().all())

        created = 0
        for tenant_id, name in TENANTS:
            if tenant_id in existing:
                continue
            session.add(Tenant(id=tenant_id, name=name))
            created += 1

        await session.commit()
        logger.info("seed_complete", tenants_created=created, tenants_total=len(TENANTS))


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
