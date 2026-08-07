"""Application services — the layer holding the domain rules.

Routes translate HTTP to these calls and back; services never import FastAPI.
`tests/architecture` enforces that boundary as a fitness function.
"""

from __future__ import annotations

from .audit import ACTOR_API, ACTOR_WORKER, AuditService
from .documents import Cursor, DocumentRepository
from .intake import IntakeService, UploadOutcome, UploadRequest, sanitize_filename
from .queue import InMemoryQueue, JobQueue, RedisQueue, build_job
from .storage import (
    InMemoryStorage,
    LocalStorage,
    StorageBackend,
    build_storage,
    build_storage_key,
)

__all__ = [
    "ACTOR_API",
    "ACTOR_WORKER",
    "AuditService",
    "Cursor",
    "DocumentRepository",
    "InMemoryQueue",
    "InMemoryStorage",
    "IntakeService",
    "JobQueue",
    "LocalStorage",
    "RedisQueue",
    "StorageBackend",
    "UploadOutcome",
    "UploadRequest",
    "build_job",
    "build_storage",
    "build_storage_key",
    "sanitize_filename",
]
