"""A metrics listener for the worker process.

`prometheus_client.start_http_server` in a thread rather than an async server:
the scrape must succeed even when the event loop is saturated by OCR work,
which is precisely when the metrics are most worth having.
"""

from __future__ import annotations

from prometheus_client import start_http_server

from app.core.logging import get_logger
from securedox_observability import metrics

logger = get_logger(__name__)


def serve_metrics(port: int = 9100, *, enabled: bool = True) -> None:
    """Expose `/metrics` on `port`. A bind failure must not stop the worker."""
    if not enabled:
        logger.info("metrics_disabled")
        return
    try:
        start_http_server(port, registry=metrics.build_registry())
    except OSError as exc:
        # Losing telemetry is bad; refusing to process documents because a port
        # is taken is worse.
        logger.warning("metrics_server_failed", port=port, error=exc.strerror)
        return
    logger.info("metrics_server_started", port=port)
