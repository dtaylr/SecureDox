# Examples

## New Worker Failure Path

Require:

- `document_processing_failures_total` label or equivalent.
- Structured worker log with `correlation_id`, `document_id`, `job_id`, `status`, and `error_code`.
- Runbook update if the failure requires operator action.
