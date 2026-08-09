# Examples

## Selector Instability

Symptom: Playwright fails only on `getByText("Done")`.

Recommendation: Replace with role/test-id plus API or audit assertion. Do not
quarantine until deterministic selector work is attempted.

## Environment Failure

Symptom: API health check fails before tests start.

Recommendation: classify as environment setup, collect service logs, and rerun
after stack readiness.
