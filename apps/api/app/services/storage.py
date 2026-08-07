"""Document blob storage behind one interface.

Local disk for dev/CI, S3 for deployed environments. The interface is narrow on
purpose — put, get, delete, exists — so the fake used by unit tests is a
complete implementation rather than a partial mock that drifts from reality.

Storage keys are derived, never caller-supplied: a client-controlled key is a
path-traversal and a cross-tenant-overwrite vulnerability in one field.
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

from app.core.errors import StorageError


def build_storage_key(tenant_id: str, document_id: uuid.UUID, mime_type: str) -> str:
    """Derive a key: tenant-prefixed, date-partitioned, extension-normalised.

    The tenant prefix means an S3 bucket policy can enforce isolation at the
    infrastructure layer too, independently of application code.
    """
    suffix = {
        "application/pdf": "pdf",
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/tiff": "tif",
    }.get(mime_type, "bin")
    day = datetime.now(UTC).strftime("%Y/%m/%d")
    return f"{tenant_id}/{day}/{document_id}.{suffix}"


class StorageBackend(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def health(self) -> bool: ...


class LocalStorage(StorageBackend):
    """Filesystem-backed storage for local development and CI.

    Blocking file I/O is pushed to a thread so it cannot stall the event loop —
    a 10 MB write on the loop thread would add latency to every concurrent
    request on the same worker.
    """

    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def _resolve(self, key: str) -> Path:
        """Resolve a key inside the root, refusing anything that escapes it."""
        target = (self._root / key).resolve()
        root = self._root.resolve()
        if not target.is_relative_to(root):
            raise StorageError("Refusing to access a path outside the storage root.")
        return target

    async def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write-then-rename: a reader never observes a partial file, which
            # matters because the worker may dequeue before the write settles.
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)

        try:
            await asyncio.to_thread(_write)
        except OSError as exc:
            raise StorageError(f"Could not store object: {exc.strerror}") from exc

    async def get(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise StorageError("Stored object is missing.") from exc
        except OSError as exc:
            raise StorageError(f"Could not read object: {exc.strerror}") from exc

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        await asyncio.to_thread(path.unlink, True)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._resolve(key).is_file)

    async def health(self) -> bool:
        def _check() -> bool:
            self._root.mkdir(parents=True, exist_ok=True)
            probe = self._root / ".health"
            probe.write_bytes(b"ok")
            probe.unlink()
            return True

        try:
            return await asyncio.to_thread(_check)
        except OSError:
            return False


class InMemoryStorage(StorageBackend):
    """Test double with real semantics — no partial writes, no path escapes."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self._objects[key] = data

    async def get(self, key: str) -> bytes:
        try:
            return self._objects[key]
        except KeyError as exc:
            raise StorageError("Stored object is missing.") from exc

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._objects

    async def health(self) -> bool:
        return True


def build_storage(backend: str, local_path: str) -> StorageBackend:
    """Factory driven by `STORAGE_BACKEND`.

    S3 is intentionally not implemented yet: the local stack and CI never use
    it, and a half-written S3 client that silently no-ops is worse than an
    explicit failure at startup.
    """
    if backend == "local":
        return LocalStorage(local_path)
    raise StorageError(f"Storage backend {backend!r} is not implemented.")
