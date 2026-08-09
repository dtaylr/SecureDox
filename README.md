# SecureDox

SecureDox is a regulated document-intake platform.

It is intentionally practical: a working app, a real test framework skeleton,
security gates, release-readiness logic, observability, infrastructure assets,
MCP tooling, and agent helpers that helps QA what must be verified as code
changes quickly.

## What This Project Demonstrates

- End-to-end product thinking: login, upload, OCR stub, review, submit, audit.
- SDET architecture: API, DB, E2E, security, OCR, and contract test layers.
- DevSecOps: pre-commit, secret scan, SAST, SCA, SBOM, container scan, Dockerfile lint.
- Release governance: one JSON go/no-go decision from quality, security, reliability, and data evidence.
- SRE practice: structured logs, correlation IDs, Prometheus metrics, Grafana dashboards, alerts, and runbooks.
- Platform fundamentals: Nginx, Docker Compose hardening, Terraform, Ansible, Kubernetes/minikube, IaC scans.
- AI TestOps: MCP test architect, false-confidence review, impacted-test selection, and human review gates.

## How The System Works

1. A user signs in with demo auth.
2. The user uploads a document through the web app or API.
3. The API validates file type, size, checksum, and tenant scope.
4. The API stores the document, writes audit events, and queues a worker job.
5. The worker runs stubbed OCR, validates fields, writes extraction results, and updates status.
6. A reviewer corrects fields if needed and submits the reviewed document.
7. Audit events prove the lifecycle.

Core services:

- `apps/web`: React intake UI.
- `apps/api`: FastAPI document-intake API.
- `apps/worker`: async OCR/validation worker.
- `packages/test-framework`: reusable SDET helpers.
- `apps/mcp-test-architect`: local MCP server for AI-assisted test design.

## Test Architecture

Test layers are split by risk:

- `tests/api`: API happy and negative paths.
- `tests/db`: persisted state, audit integrity, PII policy.
- `tests/e2e`: Playwright critical workflow.
- `tests/security`: auth, IDOR, upload validation, headers, log redaction.
- `tests/ocr`: document extraction and validation scenarios.
- `tests/contract`: consumer/provider contract checks.
- `tests/observability`: dashboard, runbook, and metric asset checks.
- `tests/architecture`: platform and IaC architecture policies.

The point is not “hundreds of tests.” The point is fast evidence that maps to
real release risk.

## DevSecOps

Security is part of the workflow:

- Gitleaks blocks secrets.
- Semgrep runs SAST.
- Trivy runs dependency, filesystem, config, and container scans.
- Syft/CycloneDX SBOM artifacts are generated.
- Hadolint checks Dockerfiles.
- `security-gates.yml` and `release-gates.yml` publish evidence.

Policies live under `security/policies/`.

## Release Gates

`scripts/release-readiness.ts` reads test reports, scan output, SBOMs, flake
data, OCR quality, performance, and audit evidence. It emits:

- `reports/release-readiness.json`
- `reports/release-readiness.prom`

Any P0 blocker produces `NO-GO`.

Sample: `docs/demo/reports/sample-release-readiness.json`.

## Observability

Every request/job/log is built around correlation:

- `correlation_id`
- `user_id`
- `document_id`
- `job_id`
- `service_name`
- `event_type`
- `status`
- `latency_ms`
- `error_code`

Prometheus and Grafana assets live under `observability/`. Runbooks live under
`docs/sre-runbooks/`.

## MCP And AI TestOps

The MCP Test Architect helps AI-assisted developers move faster without blindly
trusting generated tests.

It can:

- Analyze route risk.
- Draft Playwright tests.
- Flag weak assertions and false confidence.
- Suggest missing assertions.
- Map tests to requirements.
- Detect changed routes, API contracts, DB schema, and security-sensitive files.
- Suggest impacted tests and release gates.

Generated tests require human approval before they count as release evidence.

## Platform Layer

Platform assets live under `infra/`:

- `infra/docker`: Compose and Nginx gateway.
- `infra/terraform`: local/staging module structure.
- `infra/ansible`: host hardening, Docker setup, monitoring agent.
- `infra/k8s/minikube`: Kubernetes manifests with probes, Ingress, HPA, ConfigMap, and Secret example.

## Run Locally

```bash
make bootstrap
make up
```

Open:

- Web: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Gateway: `http://localhost:8080`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

Run selected checks:

```bash
make test-api
make test-db
make test-security
make test-ocr
make test-contract
make test-observability
make test-platform
yarn gate:release
```

## Reviewer Fast Path

Start here:

`docs/START-HERE-FOR-REVIEWERS.md`

Best files to inspect first:

- `scripts/release-readiness.ts`
- `apps/mcp-test-architect/src/tools.ts`
- `packages/test-framework/src/`
- `tests/api/test_document_boundaries.py`
- `tests/db/test_integrity_boundaries.py`
- `tests/contract/`
- `observability/grafana/dashboards/`
- `infra/docker/nginx.conf`
- `infra/k8s/minikube/base/`
