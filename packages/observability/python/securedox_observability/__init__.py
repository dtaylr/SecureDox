"""Instrumentation shared by the SecureDox API and worker.

Three concerns, deliberately kept together so they cannot drift apart:
metrics definitions, PII redaction, and correlation/tracing.
"""

from __future__ import annotations

from . import metrics
from .redaction import (
    REDACTED,
    is_sensitive_key,
    redact,
    redaction_processor,
    safe_label,
    scrub_text,
)
from .tracing import (
    CORRELATION_HEADER,
    REQUEST_ID_HEADER,
    configure_tracing,
    new_correlation_id,
    sanitize_correlation_id,
    span,
)

__version__ = "0.1.0"

__all__ = [
    "CORRELATION_HEADER",
    "REDACTED",
    "REQUEST_ID_HEADER",
    "__version__",
    "configure_tracing",
    "is_sensitive_key",
    "metrics",
    "new_correlation_id",
    "redact",
    "redaction_processor",
    "safe_label",
    "sanitize_correlation_id",
    "scrub_text",
    "span",
]
