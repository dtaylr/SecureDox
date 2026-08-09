# Release Gates

The release gate converts quality, security, reliability, data integrity, and
AI-generated-test-review evidence into a single `GO` or `NO-GO` decision.

Run locally:

```bash
yarn gate:release
```

The script writes `reports/release-readiness.json` and exits non-zero on
`NO-GO`.

## Gate Categories

### Quality Gates

Blockers:

- Any critical path API or e2e test fails.
- Critical path test evidence is missing.
- Contract tests are missing or failing.
- Critical path pass rate is below `GATE_MIN_CRITICAL_PATH_PASS_RATE`.
- Flake rate exceeds `GATE_MAX_FLAKE_RATE`.

### Security Gates

Blockers:

- Any secret is found.
- Any SAST blocker is found.
- Any IDOR/security access test fails or is missing.
- Upload validation security test fails or is missing.
- Sensitive log leakage is detected or redaction evidence is missing.
- Any critical dependency vulnerability is found.
- Any critical container vulnerability is found.
- SBOM artifacts are missing.

### Reliability Gates

Blockers:

- p95 upload latency exceeds `GATE_MAX_P95_MS`.
- Error rate exceeds `GATE_MAX_ERROR_RATE`.

Missing performance evidence is a warning in early phases and can be promoted
to a blocker as the performance suite matures.

### Data Integrity Gates

Blockers:

- DB smoke test fails.
- Audit log validation fails or is missing.
- Audit sequence does not include upload and submission evidence.

### AI-Generated-Test Review Gates

Blockers:

- Any generated test listed in `tests/reports/generated-test-review.json` lacks
  human approval.

## Output

The JSON includes:

- `release_decision`
- `quality`
- `security`
- `reliability`
- `data_integrity`
- `ai_generated_tests`
- `blockers`
- `warnings`
- `evidence`
