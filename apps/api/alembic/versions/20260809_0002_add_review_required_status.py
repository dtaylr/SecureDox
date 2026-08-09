"""Add review-required document status.

Revision ID: 0003_review_required
Revises: 0002_document_submitted
Created: 2026-08-09 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_review_required"
down_revision: str | None = "0002_document_submitted"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'REVIEW_REQUIRED'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values without rebuilding dependent columns.
    pass
