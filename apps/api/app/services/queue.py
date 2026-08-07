"""Enqueueing intake jobs.

The API's only job after accepting an upload is to publish a message the worker
can act on. The payload is `securedox_shared.IntakeJob` — validated here before
it goes on the wire, so a contract break is caught at the producer rather than
as a poison message the consumer cannot parse.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.core.errors import QueueError
from securedox_shared import DocumentType, IntakeJob


class JobQueue(Protocol):
    async def enqueue(self, job: IntakeJob) -> None: ...
    async def depth(self) -> int: ...
    async def health(self) -> bool: ...


class RedisQueue:
    """Redis list used as a FIFO queue.

    A list rather than a stream: the worker pool is single-group and the
    retry/DLQ policy lives in the worker, so consumer-group bookkeeping would
    add moving parts without adding a property worth testing.
    """

    def __init__(self, redis: Redis, queue_name: str) -> None:
        self._redis = redis
        self._queue_name = queue_name

    @property
    def dead_letter_name(self) -> str:
        return f"{self._queue_name}:dead"

    async def enqueue(self, job: IntakeJob) -> None:
        # `model_dump_json` round-trips UUIDs and datetimes the way the JSON
        # schema in packages/contracts expects; hand-rolled dict building here
        # is exactly how producer/consumer drift starts.
        try:
            await self._redis.rpush(self._queue_name, job.model_dump_json())  # type: ignore[misc]
        except Exception as exc:
            raise QueueError("Could not enqueue the document for processing.") from exc

    async def depth(self) -> int:
        try:
            return int(await self._redis.llen(self._queue_name))  # type: ignore[misc]
        except Exception:
            return -1

    async def health(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False


class InMemoryQueue:
    """Test double that records published payloads for contract assertions."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def enqueue(self, job: IntakeJob) -> None:
        self.published.append(json.loads(job.model_dump_json()))

    async def depth(self) -> int:
        return len(self.published)

    async def health(self) -> bool:
        return True


def build_job(
    *,
    document_id: UUID,
    tenant_id: str,
    document_type: DocumentType,
    storage_key: str,
    mime_type: str,
    checksum_sha256: str,
    correlation_id: str,
    attempt: int = 1,
) -> IntakeJob:
    """Construct the queue message, stamping the enqueue time in UTC."""
    return IntakeJob(
        document_id=document_id,
        tenant_id=tenant_id,
        document_type=document_type,
        storage_key=storage_key,
        mime_type=mime_type,
        checksum_sha256=checksum_sha256,
        correlation_id=correlation_id,
        enqueued_at=datetime.now(UTC),
        attempt=attempt,
    )
