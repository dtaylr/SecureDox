"""Declarative base and column conventions.

Naming conventions are set explicitly so Alembic autogenerate produces stable
constraint names. Without them Postgres invents names, autogenerate sees a
"change" on every run, and the migration history fills with noise — which is
exactly the drift `tests/db` exists to catch.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import (
    UUID as PgUUID,  # noqa: N811 - conventional alias for the dialect type
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped[uuid.UUID]:
    """Primary key generated application-side.

    Client-generated so the API can log the id and return it to the caller
    before the transaction commits — the upload response and the first audit
    row must agree even if the commit later fails.
    """
    return mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """`created_at` / `updated_at` maintained by the database clock.

    Server-side defaults, not Python ones: the worker and the API run in
    separate containers whose clocks can disagree, and the audit trail must be
    orderable across both.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
