"""FastAPI dependencies.

Two rules this module exists to enforce:

* Tenant identity comes from the verified token and nowhere else. There is no
  dependency that reads a tenant from a path or query parameter, so a handler
  cannot accidentally accept one.
* Shared clients (redis, storage) are process-wide singletons held on
  `app.state`, not rebuilt per request — a connection pool per request is a
  socket exhaustion bug waiting for load.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request, params
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError
from app.core.logging import tenant_id_ctx, user_id_ctx
from app.core.security import Principal, decode_token, parse_bearer
from app.db.session import get_session
from app.services.intake import IntakeService
from app.services.queue import JobQueue
from app.services.storage import StorageBackend

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_principal(
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    """Authenticate the caller. Raises 401 on any token problem."""
    principal = decode_token(parse_bearer(authorization))
    tenant_id_ctx.set(principal.tenant_id)
    user_id_ctx.set(principal.subject)
    return principal


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_roles(*roles: str) -> params.Depends:
    """Build a dependency that admits only callers holding one of `roles`.

    Authorisation is a separate step from authentication on purpose: the 401
    and the 403 paths have different audit and metric treatment.

    Returns `Depends(...)`, not the bare function. A raw callable in an
    `Annotated[...]` is not recognised as a dependency — FastAPI would treat
    the parameter as a request body field and answer 422 where the caller
    should have seen 403.
    """

    async def _check(principal: PrincipalDep) -> Principal:
        tenant_id_ctx.set(principal.tenant_id)
        user_id_ctx.set(principal.subject)
        if not principal.has_role(*roles):
            raise ForbiddenError("Your role does not permit this operation.")
        return principal

    return Depends(_check)


def get_storage(request: Request) -> StorageBackend:
    return request.app.state.storage  # type: ignore[no-any-return]


def get_queue(request: Request) -> JobQueue:
    return request.app.state.queue  # type: ignore[no-any-return]


StorageDep = Annotated[StorageBackend, Depends(get_storage)]
QueueDep = Annotated[JobQueue, Depends(get_queue)]


async def get_intake_service(
    session: SessionDep,
    storage: StorageDep,
    queue: QueueDep,
    settings: SettingsDep,
) -> AsyncIterator[IntakeService]:
    yield IntakeService(
        session,
        storage=storage,
        queue=queue,
        allowed_mime_types=settings.allowed_mime_types,
        max_upload_bytes=settings.max_upload_bytes,
    )


IntakeDep = Annotated[IntakeService, Depends(get_intake_service)]


def get_correlation_id(request: Request) -> str:
    """The id the middleware minted or adopted for this request."""
    return getattr(request.state, "correlation_id", "unknown")


CorrelationDep = Annotated[str, Depends(get_correlation_id)]
