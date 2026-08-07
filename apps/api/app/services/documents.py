"""Document reads and the cursor pagination scheme.

Every query in this module takes `tenant_id` as a required argument rather than
reading it from ambient state. It is the pattern that makes the cross-tenant
authz tests meaningful: a missing tenant filter is a compile-time-visible
omission, not a subtle absence.
"""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateTransitionError, NotFoundError, ValidationError
from app.models import Document
from securedox_shared import DocumentStatus, DocumentType


@dataclass(frozen=True, slots=True)
class Cursor:
    """Keyset position: the sort key of the last row the client saw.

    `(created_at, id)` rather than `created_at` alone — timestamps collide
    under a burst upload, and a non-unique keyset silently drops rows.
    """

    created_at: datetime
    document_id: uuid.UUID

    def encode(self) -> str:
        payload = json.dumps(
            {"ts": self.created_at.isoformat(), "id": str(self.document_id)},
            separators=(",", ":"),
        )
        return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")

    @classmethod
    def decode(cls, raw: str) -> Cursor:
        try:
            padded = raw + "=" * (-len(raw) % 4)
            data = json.loads(base64.urlsafe_b64decode(padded))
            return cls(
                created_at=datetime.fromisoformat(data["ts"]),
                document_id=uuid.UUID(data["id"]),
            )
        except (ValueError, KeyError, TypeError, binascii.Error) as exc:
            # A malformed cursor is a client bug, not a server error — and it
            # must not surface a decode traceback.
            raise ValidationError("Invalid pagination cursor.") from exc


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, document_id: uuid.UUID, *, tenant_id: str) -> Document:
        """Fetch one document scoped to its tenant.

        A document belonging to another tenant raises NotFound, not Forbidden:
        confirming existence to a non-owner is an enumeration oracle.
        """
        stmt = select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        document = (await self._session.execute(stmt)).scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document not found.")
        return document

    async def find_by_checksum(self, checksum: str, *, tenant_id: str) -> Document | None:
        """Dedupe lookup, matching the `(tenant_id, checksum)` unique index."""
        stmt = select(Document).where(
            Document.tenant_id == tenant_id, Document.checksum_sha256 == checksum
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        tenant_id: str,
        limit: int = 25,
        cursor: Cursor | None = None,
        status: DocumentStatus | None = None,
        document_type: DocumentType | None = None,
    ) -> tuple[list[Document], Cursor | None]:
        """One page, newest first, plus the cursor for the next one.

        Fetches `limit + 1` rows to answer "is there more?" without a second
        count query — a COUNT over a large tenant is the slowest thing on the
        page and the answer is never used for anything but a boolean.
        """
        stmt: Select[tuple[Document]] = (
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit + 1)
        )

        if status is not None:
            stmt = stmt.where(Document.status == status)
        if document_type is not None:
            stmt = stmt.where(Document.document_type == document_type)
        if cursor is not None:
            stmt = stmt.where(
                or_(
                    Document.created_at < cursor.created_at,
                    and_(
                        Document.created_at == cursor.created_at,
                        Document.id < cursor.document_id,
                    ),
                )
            )

        rows = list((await self._session.execute(stmt)).scalars().all())
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = (
            Cursor(created_at=page[-1].created_at, document_id=page[-1].id)
            if has_more and page
            else None
        )
        return page, next_cursor

    async def mark_processed(
        self, document: Document, *, status: DocumentStatus, reason: str | None = None
    ) -> Document:
        """Move a document to a terminal status, refusing illegal transitions."""
        if not document.can_move_to(status):
            raise InvalidStateTransitionError(
                f"Cannot move a document from {document.status.value} to {status.value}."
            )
        document.status = status
        document.rejection_reason = reason
        document.processed_at = datetime.now(UTC)
        return document
