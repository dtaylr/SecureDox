"""Correlation identifiers and optional OpenTelemetry wiring.

The correlation id is the spine of every incident investigation in this repo:
it is minted at upload, travels on the queue message, is stamped on every log
line by `app.core.logging`, and is stored on the audit row — so a support
ticket quoting one id yields the whole story across three services.

OpenTelemetry is optional on purpose. The local stack ships Prometheus + Loki
only, and CI must not require a collector, so tracing degrades to a no-op when
the SDK is absent or `OTEL_EXPORTER_OTLP_ENDPOINT` is unset.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Final

CORRELATION_HEADER: Final = "X-Correlation-ID"
REQUEST_ID_HEADER: Final = "X-Request-ID"

#: Accepts our own ids and W3C trace ids so an upstream gateway's value can be
#: adopted rather than replaced. Anything else is rejected — an unvalidated
#: header would let a caller inject newlines into the log stream.
_VALID_ID: Final = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def new_correlation_id() -> str:
    """Mint an id: short, URL-safe, and greppable across all three services."""
    return f"sdx-{uuid.uuid4().hex[:20]}"


def sanitize_correlation_id(candidate: str | None) -> str:
    """Adopt a caller-supplied id when it is well-formed, else mint a fresh one."""
    if candidate and _VALID_ID.match(candidate):
        return candidate
    return new_correlation_id()


def configure_tracing(*, service_name: str, service_version: str) -> bool:
    """Install OTLP tracing when the SDK and an endpoint are both available.

    Returns True when tracing is live, so the caller can log which mode it is
    running in — silent degradation is how you end up debugging an incident
    with no spans and no idea why.
    """
    import os

    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return False

    resource = Resource.create({"service.name": service_name, "service.version": service_version})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    return True


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Open a span when tracing is configured; a no-op otherwise.

    Call sites stay identical whether or not a collector is running, which is
    what keeps the CI and local stacks honest about the same code path.
    """
    try:
        from opentelemetry import trace
    except ImportError:
        yield
        return

    tracer = trace.get_tracer("securedox")
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            current.set_attribute(key, value)
        yield
