"""Prometheus metrics for the intake pipeline.

Every metric here is referenced by a Grafana panel in
`observability/grafana/dashboards/` or by an alert rule in
`observability/prometheus/`. Adding a metric is cheap; adding a *label* is not,
so labels are restricted to bounded vocabularies (tenant, document type,
status, rule id, severity) and every free-form string goes through
`redaction.safe_label` first.

The API runs multi-process under uvicorn workers, so registry creation honours
`PROMETHEUS_MULTIPROC_DIR` when it is set.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from prometheus_client.core import CollectorRegistry as _Registry

CONTENT_TYPE: Final = "text/plain; version=0.0.4; charset=utf-8"

#: Shared registry. Services register their own collectors against it rather
#: than the global default so tests can build a clean one per case.
REGISTRY: Final[CollectorRegistry] = CollectorRegistry()

# --- Buckets ---------------------------------------------------------------
# Tuned to the SLOs in docs/sre-runbooks: API p95 < 800ms, end-to-end
# processing p95 < 30s. Buckets straddle each objective so the histogram
# quantile is accurate near the threshold that actually matters.
_API_BUCKETS: Final = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.8, 1.0, 2.5, 5.0, 10.0)
_PIPELINE_BUCKETS: Final = (0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0, 300.0)
_CONFIDENCE_BUCKETS: Final = (0.0, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0)


# --- HTTP ------------------------------------------------------------------
http_requests_total = Counter(
    "securedox_http_requests_total",
    "HTTP requests handled by the API.",
    ("method", "route", "status"),
    registry=REGISTRY,
)

# Phase 8 canonical alias. Prometheus exposes it as
# `http_requests_total`; existing Securedox-prefixed dashboards keep working.
canonical_http_requests_total = Counter(
    "http_requests_total",
    "HTTP requests handled by service.",
    ("method", "route", "status"),
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "API request latency.",
    ("method", "route"),
    buckets=_API_BUCKETS,
    registry=REGISTRY,
)

# --- Intake ----------------------------------------------------------------
documents_received_total = Counter(
    "securedox_documents_received_total",
    "Documents accepted at the upload endpoint.",
    ("tenant_id", "document_type"),
    registry=REGISTRY,
)

documents_rejected_at_gate_total = Counter(
    "securedox_documents_rejected_at_gate_total",
    "Uploads refused before queueing (mime, size or checksum gate).",
    ("tenant_id", "reason"),
    registry=REGISTRY,
)

upload_rejections_total = Counter(
    "upload_rejections_total",
    "Uploads refused before queueing (mime, size or checksum gate).",
    ("tenant_id", "reason"),
    registry=REGISTRY,
)

document_status_transitions_total = Counter(
    "securedox_document_status_transitions_total",
    "State machine transitions, by source and target status.",
    ("from_status", "to_status"),
    registry=REGISTRY,
)

documents_in_flight = Gauge(
    "securedox_documents_in_flight",
    "Documents in a non-terminal status right now.",
    ("status",),
    registry=REGISTRY,
    multiprocess_mode="livesum",
)

# --- Queue / worker --------------------------------------------------------
queue_depth = Gauge(
    "securedox_queue_depth",
    "Jobs waiting on the intake queue.",
    ("queue",),
    registry=REGISTRY,
    multiprocess_mode="liveall",
)

jobs_processed_total = Counter(
    "securedox_jobs_processed_total",
    "Worker jobs finished, by outcome.",
    ("outcome",),
    registry=REGISTRY,
)

job_retries_total = Counter(
    "securedox_job_retries_total",
    "Worker job retry attempts, by failure class.",
    ("reason",),
    registry=REGISTRY,
)

processing_duration_seconds = Histogram(
    "document_processing_duration_seconds",
    "Wall-clock time from dequeue to terminal status.",
    ("document_type",),
    buckets=_PIPELINE_BUCKETS,
    registry=REGISTRY,
)

document_processing_failures_total = Counter(
    "document_processing_failures_total",
    "Document processing failures by reason.",
    ("reason",),
    registry=REGISTRY,
)

# --- OCR -------------------------------------------------------------------
ocr_duration_seconds = Histogram(
    "securedox_ocr_duration_seconds",
    "Time spent inside the OCR adapter.",
    ("provider",),
    buckets=_PIPELINE_BUCKETS,
    registry=REGISTRY,
)

ocr_field_confidence = Histogram(
    "ocr_confidence_score",
    "Per-field OCR confidence. Feeds the false-confidence reliability check.",
    ("document_type",),
    buckets=_CONFIDENCE_BUCKETS,
    registry=REGISTRY,
)

ocr_failures_total = Counter(
    "securedox_ocr_failures_total",
    "OCR adapter errors, by provider and error class.",
    ("provider", "error"),
    registry=REGISTRY,
)

# --- Validation ------------------------------------------------------------
validation_outcomes_total = Counter(
    "securedox_validation_outcomes_total",
    "Rule evaluations, by rule and outcome. Drives the rejection-reason panel.",
    ("rule_id", "severity", "outcome"),
    registry=REGISTRY,
)

# --- Audit -----------------------------------------------------------------
audit_events_total = Counter(
    "securedox_audit_events_total",
    "Audit trail rows written, by action.",
    ("action",),
    registry=REGISTRY,
)

security_access_denied_total = Counter(
    "security_access_denied_total",
    "Access denied responses by reason.",
    ("reason",),
    registry=REGISTRY,
)

rate_limit_triggered_total = Counter(
    "rate_limit_triggered_total",
    "Rate limit responses by route.",
    ("route",),
    registry=REGISTRY,
)

release_gate_failures_total = Counter(
    "release_gate_failures_total",
    "Release gate failures by gate category.",
    ("gate",),
    registry=REGISTRY,
)

test_flake_rate = Gauge(
    "test_flake_rate",
    "Most recent observed test flake rate as a ratio.",
    registry=REGISTRY,
    multiprocess_mode="liveall",
)

critical_path_pass_rate = Gauge(
    "critical_path_pass_rate",
    "Most recent critical path pass rate as a ratio.",
    registry=REGISTRY,
    multiprocess_mode="liveall",
)


@contextmanager
def observe(histogram: Histogram, **labels: str) -> Iterator[None]:
    """Time a block into `histogram`, recording even when it raises.

    `Histogram.time()` would do the same, but this keeps the label-sanitising
    in one place and reads better at the three call sites that need it.
    """
    started = time.perf_counter()
    try:
        yield
    finally:
        histogram.labels(**labels).observe(time.perf_counter() - started)


def build_registry() -> _Registry:
    """Return the registry to expose on `/metrics`.

    Under multiprocess uvicorn each worker writes to its own mmap file; the
    scrape must aggregate them, otherwise counters appear to jump backwards
    as the load balancer moves between workers.
    """
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return registry
    return REGISTRY


def render() -> bytes:
    """Serialise the current metric values for a scrape."""
    return generate_latest(build_registry())
