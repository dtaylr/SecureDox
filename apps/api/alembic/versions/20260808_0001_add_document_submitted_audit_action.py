"""Add document submission audit action.

Revision ID: 0002_document_submitted
Revises: 0001_initial
Created: 2026-08-08 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_document_submitted"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'DOCUMENT_SUBMITTED'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values without rebuilding dependent columns.
    # Keeping the value is safe and avoids a destructive local downgrade.
    pass
