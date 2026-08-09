from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _database_url() -> str:
    raw = os.getenv(
        "DATABASE_URL_SYNC",
        os.getenv(
            "DATABASE_URL",
            "postgresql://securedox:securedox_local_pw@localhost:5432/securedox",
        ),
    )
    return raw.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgresql+asyncpg://", "postgresql://"
    )


@contextmanager
def db_connection() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    with psycopg.connect(_database_url(), row_factory=dict_row) as connection:
        yield connection


def get_document(document_id: str) -> dict[str, Any] | None:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id::text, tenant_id, document_type::text, status::text,
                       original_filename, correlation_id, processed_at
                  from documents
                 where id = %s
                """,
                (document_id,),
            )
            return cursor.fetchone()


def audit_events_for_document(document_id: str) -> list[dict[str, Any]]:
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id::text, tenant_id, document_id::text, action::text,
                       actor, correlation_id, detail, created_at
                  from audit_events
                 where document_id = %s
                 order by created_at asc
                """,
                (document_id,),
            )
            return list(cursor.fetchall())
