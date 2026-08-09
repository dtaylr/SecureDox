# Risk-Based Test Strategy

SecureDox handles regulated document intake, OCR extraction, review, submission,
and audit evidence. Testing is prioritized by release risk rather than by raw
test count.

## Risk Model

| Risk Area | Business Impact | Primary Evidence |
| --- | --- | --- |
| Authentication and tenant isolation | Unauthorized access to regulated documents | Security specs, IDOR tests, auth tests |
| Upload and processing path | Intake outage or broken customer workflow | Critical path API/e2e smoke tests |
| Audit trail integrity | Loss of regulatory evidence | DB tests, audit sequence assertions |
| OCR and validation correctness | Incorrect review decisions | Fixture-driven OCR tests, validation results |
| Sensitive data handling | PII leakage into logs, errors, reports | Log redaction tests, SAST rules |
| Supply chain | Vulnerable dependencies or images | SCA, SBOM, container scans |
| Reliability | Slow or unstable intake under load | Performance summary, error rate, flake rate |

## Test Priority

P0 tests block every release:

- Login/authentication guardrails.
- Tenant isolation and IDOR tests.
- Upload, processing, review, and submit critical path.
- Audit log major-event sequence.
- Upload validation and security headers.
- Secret scan, SAST blockers, dependency and container critical vulnerabilities.

P1 tests should pass before planned releases:

- Broader document type coverage.
- API pagination/filtering.
- Retry and dead-letter worker paths.
- Cross-browser web smoke.

P2 tests guide hardening and regression confidence:

- Exploratory edge cases.
- Visual polish checks.
- Longer performance and chaos scenarios.

## Evidence Sources

- `reports/junit-api.xml`
- `reports/junit-db.xml`
- `reports/junit-security.xml`
- `reports/junit-contract.xml`
- `tests/reports/playwright-results.json`
- `tests/reports/security-playwright-results.json`
- `reports/performance-summary.json`
- `reports/flake-summary.json`
- `reports/gitleaks.sarif`
- `reports/semgrep.sarif`
- `reports/trivy-fs.json`
- `reports/trivy-images.json`
- `security/sbom/*.json`

Missing P0 evidence is treated as a release blocker.
