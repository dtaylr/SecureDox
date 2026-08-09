# OCR Failure Spike

Alert: `OcrFailureSpike`

## Signals

- `securedox_ocr_failures_total` increases by provider.
- `document_processing_failures_total` increases with OCR-related reasons.
- Documents move to `FAILED` or repeatedly retry with the same `job_id`.

## Trace One Document

1. Find a failed `document_id` in worker logs.
2. Search by `correlation_id` across API and worker logs.
3. Verify worker log context includes `job_id`, `service_name=securedox-worker`, `event_type=document_job`, `error_code`, and `status`.
4. Check audit events for `EXTRACTION_STARTED` without `EXTRACTION_COMPLETED`, or `PROCESSING_FAILED`.

## Triage

- If only the vendor adapter fails, check vendor availability, timeout, and credentials.
- If mock/tesseract fails locally, inspect malformed fixture content and worker exceptions.
- If failures are transient, confirm retries and dead-letter counts stay within policy.

## Mitigation

- Fail closed: preserve failure reason and route affected documents to manual review.
- Reduce worker concurrency if the OCR backend is throttling.
- Roll back the OCR adapter change if the spike correlates with a deploy.

## Verification

- OCR failure rate returns to baseline.
- A clean fixture extracts required fields.
- Audit lifecycle includes `EXTRACTION_STARTED`, `EXTRACTION_COMPLETED`, and `VALIDATION_COMPLETED`.

## Failure Injection Drill

Run the worker with an invalid `OCR_VENDOR_URL` while `OCR_PROVIDER=vendor`. Upload a fixture document and confirm retries, `document_processing_failures_total`, worker error logs, and the dead-letter path behave as expected.
