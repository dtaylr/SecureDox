"""Application factory and process lifecycle.

`create_app()` rather than a module-level singleton: the test suites build an
app per fixture with substituted storage and queue backends, which is only
possible if construction is a function call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import root_router
from app.api.v1 import router as v1_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine
from app.observability import (
    CorrelationMiddleware,
    MetricsMiddleware,
    SecurityHeadersMiddleware,
)
from app.schemas.common import ErrorBody, ErrorDetail, ErrorResponse
from app.services.queue import RedisQueue
from app.services.storage import build_storage
from securedox_observability import configure_tracing

logger = get_logger(__name__)


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    correlation_id: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            correlation_id=correlation_id,
            details=details or [],
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={"X-SecureDox-Error-Code": code},
    )


def _correlation_of(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unknown")


def register_exception_handlers(app: FastAPI) -> None:
    """Funnel every failure into the one error envelope.

    Four handlers, because FastAPI raises three exception families and Python
    raises the fourth. Without all four, a client would occasionally receive
    FastAPI's default `{"detail": ...}` shape and every client parser would
    need two code paths.
    """

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        correlation_id = _correlation_of(request)
        # 4xx is the caller's problem and is logged at warning; 5xx is ours.
        log = logger.warning if exc.http_status < 500 else logger.error
        log("request_failed", code=exc.code, status=exc.http_status, error=exc.message)
        return _error_response(
            status_code=exc.http_status,
            code=exc.code,
            message=exc.message,
            correlation_id=correlation_id,
            details=[ErrorDetail(**d) for d in exc.details],
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's `input` echoes the offending value, which for this API is
        # frequently document content — kept out of the response entirely.
        details = [
            ErrorDetail(
                field=".".join(str(p) for p in err.get("loc", ())[1:]) or None,
                message=str(err.get("msg", "invalid value")),
            )
            for err in exc.errors()
        ]
        return _error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="The request payload failed validation.",
            correlation_id=_correlation_of(request),
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code="HTTP_ERROR",
            message=str(exc.detail),
            correlation_id=_correlation_of(request),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # The traceback goes to the log with the correlation id; the client
        # gets nothing but that id. An exception message here is untrusted
        # output that may quote document contents.
        logger.exception("unhandled_exception", error_type=type(exc).__name__)
        return _error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            correlation_id=_correlation_of(request),
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared clients on startup, close them on shutdown.

    Built once and stashed on `app.state`: a pool per request would exhaust
    file descriptors under any real load.
    """
    settings: Settings = get_settings()
    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        service=settings.service_name,
        version=settings.service_version,
    )
    tracing_on = configure_tracing(
        service_name=settings.service_name, service_version=settings.service_version
    )

    app.state.redis = Redis.from_url(str(settings.redis_url), decode_responses=True)
    app.state.queue = RedisQueue(app.state.redis, settings.queue_name)
    app.state.storage = build_storage(settings.storage_backend, settings.storage_local_path)

    logger.info(
        "api_started",
        environment=settings.securedox_env,
        storage_backend=settings.storage_backend,
        ocr_provider=settings.ocr_provider,
        tracing=tracing_on,
    )
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await dispose_engine()
        logger.info("api_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="SecureDox Intake API",
        version=settings.service_version,
        description=(
            "Regulated document intake: upload, OCR extraction, rule validation "
            "and an append-only audit trail."
        ),
        lifespan=lifespan,
        # Interactive docs are a live request forge against a system holding
        # PII; useful locally, never exposed in production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    # Added last-to-first: Starlette runs middleware in reverse registration
    # order, so correlation ends up outermost and wraps everything below it.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
        expose_headers=["X-Correlation-ID"],
        max_age=600,
    )

    register_exception_handlers(app)

    app.include_router(root_router)
    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()
