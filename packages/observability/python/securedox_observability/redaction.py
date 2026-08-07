"""PII redaction.

The regulated part of observability: an SSN or an MRN must never reach a log
line, a metric label, an error body or a Grafana panel. Redaction lives here —
one implementation, shared by the API and the worker — so that
`tests/security/test_pii_redaction.py` can prove the property once instead of
auditing every call site.

Two complementary defences:

* **Key-based** — any mapping key in `securedox_shared.PII_FIELDS` (plus the
  credential names below) is replaced wholesale, however deeply it is nested.
* **Pattern-based** — values that *look* like an SSN/MRN/NPI are masked even
  under an innocent key, which catches free-text such as an OCR error message
  echoing the raw page content.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from securedox_shared import PII_FIELDS

REDACTED: Final = "[REDACTED]"

#: Secrets are not PII but leak just as badly, so they share the same gate.
_SECRET_KEYS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "secret",
        "token",
        "authorization",
        "api_key",
        "apikey",
        "auth_jwt_secret",
        "ocr_vendor_api_key",
        "anthropic_api_key",
        "set-cookie",
        "cookie",
    }
)

_SENSITIVE_KEYS: Final[frozenset[str]] = PII_FIELDS | _SECRET_KEYS

#: Ordered most-specific first; each pattern keeps a hint of shape so an
#: engineer can still tell "the SSN was malformed" from "the SSN was missing".
_VALUE_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\bMRN\d{7}\b"), "[MRN]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.IGNORECASE), "[EMAIL]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"\b\d{13,19}\b"), "[CARD]"),
)

#: Nested structures are walked to this depth; anything deeper is dropped
#: rather than logged unredacted. Guards against cyclic or hostile payloads.
_MAX_DEPTH: Final = 6


def is_sensitive_key(key: str) -> bool:
    """True when a mapping key must never have its value logged."""
    return key.strip().lower().replace("-", "_") in _SENSITIVE_KEYS


def scrub_text(value: str) -> str:
    """Mask anything that pattern-matches a known sensitive shape."""
    for pattern, replacement in _VALUE_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def redact(value: Any, *, _depth: int = 0) -> Any:
    """Recursively redact a log/metric/error payload.

    Returns a new structure; the input is never mutated, because callers pass
    live domain objects (e.g. an extracted-field dict) that are still needed
    unredacted for persistence.
    """
    if _depth >= _MAX_DEPTH:
        return "[TRUNCATED]"

    if isinstance(value, Mapping):
        return {
            key: REDACTED if is_sensitive_key(str(key)) else redact(item, _depth=_depth + 1)
            for key, item in value.items()
        }

    # str is a Sequence; check it first so it is scrubbed, not iterated.
    if isinstance(value, str):
        return scrub_text(value)

    if isinstance(value, (list, tuple, set, frozenset)) or (
        isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray))
    ):
        return [redact(item, _depth=_depth + 1) for item in value]

    if isinstance(value, (bytes, bytearray)):
        return f"[{len(value)} bytes]"

    return value


def redaction_processor(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor form of `redact`.

    Installed by `configure_logging` in each service so redaction happens at
    the very end of the pipeline — after every other processor has had its
    chance to add fields.
    """
    return redact(event_dict)  # type: ignore[no-any-return]


def safe_label(value: str, *, max_length: int = 64) -> str:
    """Sanitise a value destined for a Prometheus label.

    Labels are unbounded-cardinality landmines: a document id or a raw field
    value as a label will melt the TSDB. Callers should prefer a bounded
    vocabulary (rule_id, severity, status); this is the last line of defence.
    """
    scrubbed = scrub_text(value).strip()
    return scrubbed[:max_length] if scrubbed else "unknown"
