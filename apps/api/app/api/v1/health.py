"""Liveness, readiness and metrics.

Unauthenticated by design — a probe that needs a token fails during exactly the
outage it exists to detect. They are also excluded from the audit trail and from
request metrics, or the kubelet's probe traffic would dominate every panel.

Liveness and readiness answer different questions, and conflating them causes
restart storms: liveness is "is this process wedged?" (restart me), readiness is
"can I serve traffic right now?" (take me out of rotation). A dead database
means not-ready, never not-alive.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import QueueDep, SessionDep, SettingsDep, StorageDep
from app.schemas.common import HealthResponse, ReadinessResponse
from securedox_observability import metrics

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: SettingsDep) -> HealthResponse:
    """Cheap and dependency-free: if the event loop can answer, we are alive."""
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.service_version,
        environment=settings.securedox_env,
    )


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def ready(
    session: SessionDep,
    storage: StorageDep,
    queue: QueueDep,
    response: Response,
) -> ReadinessResponse:
    """Check every dependency the request path actually needs.

    Each check is reported individually rather than collapsed to a boolean, so
    an on-call engineer reading the probe output learns *which* dependency is
    down without opening a dashboard.
    """
    checks: dict[str, object] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"

    checks["storage"] = "ok" if await storage.health() else "error"
    checks["queue"] = "ok" if await queue.health() else "error"

    depth = await queue.depth()
    if depth >= 0:
        checks["queue_depth"] = depth
        metrics.queue_depth.labels(queue="intake").set(depth)

    healthy = all(value == "ok" for key, value in checks.items() if key != "queue_depth")
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(status="ready" if healthy else "degraded", checks=checks)


@router.get("/metrics", include_in_schema=False, summary="Prometheus scrape endpoint")
async def prometheus_metrics() -> Response:
    return Response(content=metrics.render(), media_type=metrics.CONTENT_TYPE)
