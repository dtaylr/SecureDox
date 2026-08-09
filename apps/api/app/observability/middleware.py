"""Request middleware: correlation, metrics, security headers.

Ordering matters and is asserted by `tests/security/headers`. Correlation runs
outermost so that every log line — including one emitted by the error handler —
carries an id.

Metrics label routes by their *template* (`/api/v1/documents/{document_id}`),
never by the concrete path. Labelling by concrete path would mint one time
series per document id and take Prometheus down; `tests/api` asserts the
cardinality stays bounded.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import (
    correlation_id_ctx,
    document_id_ctx,
    error_code_ctx,
    event_type_ctx,
    get_logger,
    latency_ms_ctx,
    status_ctx,
    tenant_id_ctx,
    user_id_ctx,
)
from securedox_observability import (
    CORRELATION_HEADER,
    metrics,
    sanitize_correlation_id,
)

logger = get_logger(__name__)

#: Probes and the scrape endpoint are excluded from request metrics: at a
#: 10-second scrape interval they would otherwise be the busiest "route" in
#: every dashboard.
_UNINSTRUMENTED = frozenset({"/health", "/ready", "/metrics"})

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # The API serves JSON and file downloads only, so it needs no script,
    # style or frame sources at all.
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    ),
}


def _route_template(request: Request) -> str:
    """The matched route pattern, or a constant for unmatched paths.

    Unmatched requests (404s, scanners) collapse to one label rather than one
    per probed URL — otherwise a directory-busting scan becomes a metrics DoS.
    """
    route = request.scope.get("route")
    path_format = getattr(route, "path_format", None) or getattr(route, "path", None)
    return str(path_format) if path_format else "unmatched"


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Adopt or mint a correlation id and bind it for the request's lifetime."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = sanitize_correlation_id(request.headers.get(CORRELATION_HEADER))
        request.state.correlation_id = correlation_id
        token = correlation_id_ctx.set(correlation_id)
        tenant_token = tenant_id_ctx.set(None)
        user_token = user_id_ctx.set(None)
        document_token = document_id_ctx.set(None)
        event_token = event_type_ctx.set("http_request")
        status_token = status_ctx.set(None)
        latency_token = latency_ms_ctx.set(None)
        error_token = error_code_ctx.set(None)
        try:
            response = await call_next(request)
        finally:
            correlation_id_ctx.reset(token)
            tenant_id_ctx.reset(tenant_token)
            user_id_ctx.reset(user_token)
            document_id_ctx.reset(document_token)
            event_type_ctx.reset(event_token)
            status_ctx.reset(status_token)
            latency_ms_ctx.reset(latency_token)
            error_code_ctx.reset(error_token)

        # Echoed so a client can quote it in a support ticket without having to
        # find it in a response body that may be an error envelope.
        response.headers[CORRELATION_HEADER] = correlation_id
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _UNINSTRUMENTED:
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        error_code: str | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            error_code = response.headers.get("X-SecureDox-Error-Code")
            return response
        finally:
            # In `finally` so an unhandled exception still records a 500 — the
            # requests that fail hardest are the ones you most need counted.
            route = _route_template(request)
            if document_id := request.path_params.get("document_id"):
                document_id_ctx.set(str(document_id))
            elapsed = time.perf_counter() - started
            latency_ms = round(elapsed * 1000, 3)
            status_ctx.set(str(status_code))
            latency_ms_ctx.set(latency_ms)
            if error_code:
                error_code_ctx.set(error_code)
            metrics.http_requests_total.labels(
                method=request.method, route=route, status=str(status_code)
            ).inc()
            metrics.canonical_http_requests_total.labels(
                method=request.method, route=route, status=str(status_code)
            ).inc()
            metrics.http_request_duration_seconds.labels(
                method=request.method, route=route
            ).observe(elapsed)
            if status_code == 401:
                metrics.security_access_denied_total.labels(reason="unauthorized").inc()
            elif status_code == 403:
                metrics.security_access_denied_total.labels(reason="forbidden").inc()
            elif status_code == 429:
                metrics.rate_limit_triggered_total.labels(route=route).inc()
            logger.info(
                "http_request_complete",
                method=request.method,
                route=route,
                status=str(status_code),
                latency_ms=latency_ms,
                error_code=error_code,
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply hardening headers to every response, including error responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
