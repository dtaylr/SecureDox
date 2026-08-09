# Release Gate Failure

Alert: `ReleaseGateFailure`

## Signals

- `release_gate_failures_total` increases by gate category.
- `reports/release-readiness.json` has `release_decision` set to `NO-GO`.
- CI uploads `reports/release-readiness.prom` and JSON evidence.

## Triage

1. Open `reports/release-readiness.json`.
2. Review `blockers` first, then `warnings`.
3. Map each blocker to `quality`, `security`, `reliability`, `data_integrity`, or `ai_generated_tests`.
4. Do not override a blocker without written evidence and reviewer approval.

## Common Causes

- Missing SBOM or scan artifacts.
- Contract, OCR, or critical path tests missing or failed.
- Container image has a critical vulnerability.
- Audit sequence validation is missing.

## Mitigation

- Regenerate missing evidence when the suite did not run.
- Fix product defects when evidence ran and failed.
- Re-run `yarn gate:release` only after the root cause is addressed.

## Verification

- `release_decision` is `GO`.
- `release_gate_failures_total` has no new increments for the release attempt.
- The release summary artifact is attached to CI.

## Failure Injection Drill

Run `node --experimental-strip-types scripts/release-readiness.ts --no-fail` with scan/test evidence removed. Confirm it produces `NO-GO`, writes `reports/release-readiness.prom`, and increments gate categories in the artifact.
