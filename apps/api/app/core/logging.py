"""Structured logging.

Every log line is JSON with a stable field set so Loki/Grafana queries and the
`observability/logs/sample-events.json` contract stay in sync. The
`correlation_id` binds an upload to every downstream worker log and audit row.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from securedox_observability import redaction_processor

correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
tenant_id_ctx: ContextVar[str | None] = ContextVar("tenant_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
document_id_ctx: ContextVar[str | None] = ContextVar("document_id", default=None)
job_id_ctx: ContextVar[str | None] = ContextVar("job_id", default=None)
event_type_ctx: ContextVar[str | None] = ContextVar("event_type", default=None)
status_ctx: ContextVar[str | None] = ContextVar("status", default=None)
latency_ms_ctx: ContextVar[float | None] = ContextVar("latency_ms", default=None)
error_code_ctx: ContextVar[str | None] = ContextVar("error_code", default=None)


def _inject_context(
    _logger: Any, _method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    if (cid := correlation_id_ctx.get()) is not None:
        event_dict.setdefault("correlation_id", cid)
    if (tid := tenant_id_ctx.get()) is not None:
        event_dict.setdefault("tenant_id", tid)
    if (uid := user_id_ctx.get()) is not None:
        event_dict.setdefault("user_id", uid)
    if (doc_id := document_id_ctx.get()) is not None:
        event_dict.setdefault("document_id", doc_id)
    if (job_id := job_id_ctx.get()) is not None:
        event_dict.setdefault("job_id", job_id)
    if (event_type := event_type_ctx.get()) is not None:
        event_dict.setdefault("event_type", event_type)
    if (status := status_ctx.get()) is not None:
        event_dict.setdefault("status", status)
    if (latency_ms := latency_ms_ctx.get()) is not None:
        event_dict.setdefault("latency_ms", latency_ms)
    if (error_code := error_code_ctx.get()) is not None:
        event_dict.setdefault("error_code", error_code)
    return event_dict


def configure_logging(
    *,
    level: str = "INFO",
    fmt: str = "json",
    service: str = "securedox-api",
    version: str = "0.0.0",
) -> None:
    """Install a structlog pipeline shared by the API and the worker."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _inject_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redaction_processor,
    ]

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route stdlib loggers (uvicorn, sqlalchemy) through the same renderer.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    for noisy in ("uvicorn.access", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).handlers.clear()
        logging.getLogger(noisy).propagate = True

    structlog.contextvars.bind_contextvars(service=service, service_name=service, version=version)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
