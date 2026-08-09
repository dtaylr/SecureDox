# Document Processing Latency

Alert: `DocumentProcessingLatencyHigh`

## Signals

- `document_processing_duration_seconds` p95 is above 30 seconds for 10 minutes.
- `securedox_queue_depth{queue="intake"}` is rising.
- API documents remain in `QUEUED`, `EXTRACTING`, or `VALIDATING`.

## Trace One Document

1. Copy `correlation_id` from the upload response, audit log, or API response header.
2. Search logs for that `correlation_id`.
3. Confirm all log lines include `service_name`, `event_type`, `document_id`, `job_id`, `status`, and `latency_ms`.
4. Query audit events for the `document_id` and compare the last event with the current document status.

## Triage

- If queue depth is high and worker logs are healthy, scale worker replicas.
- If OCR latency dominates, follow `ocr-failure-spike.md`.
- If database checks are degraded, remove API from rotation through readiness and inspect Postgres.
- If logs show repeated retries for one `job_id`, inspect the dead-letter queue.

## Mitigation

- Increase worker concurrency only if CPU and database connections have headroom.
- Temporarily route low-confidence documents to manual review rather than retrying extraction.
- Keep audit logging enabled; do not disable evidence creation during mitigation.

## Verification

- p95 processing latency returns below 30 seconds.
- Queue depth returns to baseline.
- New upload correlation IDs show `DOCUMENT_UPLOADED`, `DOCUMENT_QUEUED`, `EXTRACTION_COMPLETED`, and `VALIDATION_COMPLETED`.

## Failure Injection Drill

Set `OCR_DEGRADATION_RATE=1.0` for the worker in a local stack and upload five fixture documents. Confirm latency and manual-review signals rise, dashboards update, and this runbook identifies the OCR path as the bottleneck.
