# Start Here For Reviewers

This repo is designed to be reviewable in 90 seconds and credible in 10
minutes.

## 1. System Design Overview

Read:

- `README.md`
- `docs/system-design/platform-infrastructure.md`
- `docs/architecture/system-context.mmd`

Look for: product workflow, service boundaries, worker queue, audit trail, and
correlation IDs.

## 2. Test Architecture

Read:

- `docs/qa-strategy/risk-based-test-strategy.md`
- `packages/test-framework/src/`
- `tests/api/test_document_boundaries.py`
- `tests/db/test_integrity_boundaries.py`
- `tests/contract/`

Look for: tests mapped to real risks, not shallow UI-only checks.

## 3. DevSecOps Pipeline

Read:

- `.github/workflows/security-gates.yml`
- `security/policies/`
- `scripts/generate-sbom.sh`
- `scripts/scan-container.sh`

Look for: secret scanning, SAST, SCA, SBOM, Dockerfile linting, and image scans.

## 4. Release Readiness Report

Read:

- `scripts/release-readiness.ts`
- `docs/demo/reports/sample-release-readiness.json`
- `docs/qa-strategy/release-gates.md`

Look for: one go/no-go decision from quality, security, reliability, data, and
AI-generated-test review evidence.

## 5. MCP / AI TestOps Workflow

Read:

- `apps/mcp-test-architect/src/tools.ts`
- `docs/qa-strategy/ai-generated-test-review-checklist.md`
- `security/policies/mcp-test-architect-policy.yml`
- `agents/`
- `skills/`

Look for: AI test generation treated as a draft, with false-confidence review
and human approval before merge.

## 6. Observability Dashboards

Read:

- `observability/grafana/dashboards/`
- `observability/prometheus/alerts.yml`
- `docs/demo/screenshots/grafana-service-health.svg`

Look for: metrics, alerts, runbooks, and correlation IDs that trace one request
from web to API to worker.

## 7. Security Mapping

Read:

- `docs/security/security-release-gates.md`
- `tests/security/`
- `security/gitleaks/gitleaks.toml`
- `security/semgrep/rules.yml`
- `security/trivy/trivy.yaml`

Look for: IDOR tests, upload validation, log redaction, secret detection, and
container vulnerability blockers.

## 8. Runbooks

Read:

- `docs/sre-runbooks/document-processing-latency.md`
- `docs/sre-runbooks/ocr-failure-spike.md`
- `docs/sre-runbooks/release-gate-failure.md`
- `docs/sre-runbooks/security/idor-attempts-spike.md`
- `docs/sre-runbooks/security/secret-detected-in-ci.md`

Look for: diagnosis steps, metrics, correlation IDs, mitigation, and failure
injection drills.

## Fast Commands

```bash
yarn agents:impacted-tests --file apps/api/app/api/v1/documents.py
yarn workspace @securedox/mcp-test-architect list-tools
node --experimental-strip-types scripts/release-readiness.ts --no-fail
```
