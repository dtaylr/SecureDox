"""Tenant — the isolation boundary every other table hangs off.

Multi-tenancy is enforced in three independent places, on purpose: the FK here,
a `tenant_id` predicate in every repository query, and the authz tests in
`tests/security/authz`. Any one of them failing alone is a bug; all three
failing together is the cross-tenant leak the suite is designed to prevent.
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("id = lower(id)", name="id_lowercase"),
        CheckConstraint("length(id) >= 2", name="id_min_length"),
    )

    #: Human-readable slug rather than a UUID: it appears in metric labels and
    #: log lines, where an opaque id would make every dashboard unreadable.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    #: Uploads above this are rejected at the gate before any bytes are stored.
    max_upload_bytes: Mapped[int] = mapped_column(nullable=False, default=10 * 1024 * 1024)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Tenant {self.id}>"
