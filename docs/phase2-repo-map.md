# Phase 2 Repo Map

Created during phase 2 to avoid re-reading the whole repo on later turns.

## Runtime Shape

- `apps/api`: FastAPI intake API with demo auth, upload gate, document reads,
  field correction, review submission, health/readiness, and admin status.
- `apps/worker`: async Redis consumer that pulls intake jobs, runs mock OCR,
  validates extracted fields, writes results, and appends audit events.
- `apps/web`: Vite React single-screen intake app for login, upload, document
  status, review, submit, and admin status.
- `packages/shared/python`: domain enums, state transitions, queue contracts,
  and validation rules shared by API and worker.
- `packages/observability/python`: metrics, tracing hooks, and PII redaction.
- `infra/docker/docker-compose.yml`: local Postgres, Redis, API, worker, web,
  and nginx gateway.

## Key Backend Entry Points

- API app factory: `apps/api/app/main.py`
- API routers: `apps/api/app/api/v1/`
- Auth dependency and roles: `apps/api/app/core/security.py`
- Upload orchestration: `apps/api/app/services/intake.py`
- Document repository: `apps/api/app/services/documents.py`
- Audit writer: `apps/api/app/services/audit.py`
- Worker loop: `apps/worker/worker/main.py`
- Worker processor: `apps/worker/worker/processor.py`
- Mock OCR adapter: `apps/worker/worker/ocr/mock.py`
- Rule runner: `apps/worker/worker/rules/runner.py`

## Phase 2 Behavior

- Authentication is mocked with JWTs from `/api/v1/auth/login`.
- Uploads are stored locally, inserted as `RECEIVED`, queued, then moved to
  `QUEUED`.
- Worker moves documents through `EXTRACTING`, `VALIDATING`, then
  `VALIDATED` or `REJECTED`.
- OCR is deterministic mock OCR; fixture bytes may include
  `SECUREDOX-FIXTURE:` JSON.
- Review corrections patch extracted fields and create `FIELD_CORRECTED`
  audit events.
- Submission records `DOCUMENT_SUBMITTED` as an audit event without adding a
  new document status.
- Admin status is tenant-scoped and reports queue depth, document counts by
  status, and recent audit events.

## Local Commands

- `make bootstrap`: create `.env`, Python venv, and JS deps.
- `make up`: build and start the stack.
- `make seed`: load demo tenants plus one processed demo document.
- `make down`: stop the stack and remove volumes.
- `yarn test:e2e`: run Playwright smoke tests from `tests/e2e`.
- `make test-api`: run pytest API smoke tests from `tests/api`.
- `make test-db`: run pytest DB smoke tests from `tests/db`.
- `make test-ocr`: run OCR/document validation tests from `tests/ocr`.

## Demo Users

All use password `securedox-demo`.

- `admin`
- `reviewer`
- `uploader`

Default tenant for the seeded demo path is `acme-lending`.

## Phase 3 Test Framework

- `packages/test-framework`: TypeScript SDET helpers for Playwright and future
  TS suites. Exposes `ApiClient`, `DbClient`, auth/user/document fixtures,
  correlation/retry/wait helpers, audit helpers, assertions, and report writers.
- `tests/e2e`: Playwright runner and critical UI/API smoke spec.
- `tests/api`: pytest API smoke covering upload, processing, review readiness,
  submission, and audit evidence.
- `tests/db`: pytest DB helper smoke validating persisted records.
- `tests/security`: pytest security smoke for unauthenticated upload rejection.
- `tests/helpers`: Python helper layer mirroring the framework primitives used
  by pytest suites.
- `tests/fixtures`: deterministic document fixtures with embedded mock OCR
  payloads.
- `tests/reports`: generated JSON/JUnit/Playwright output target.
- `tests/ocr`: OCR validation workflow tests using fixture documents under
  `test-documents/`.

## Phase 4 DevSecOps

- Pre-commit: `.pre-commit-config.yaml`, with hygiene hooks, Gitleaks,
  Semgrep, Hadolint, and repo-local approval/commit-message guards.
- Security policies: `security/policies/dependency-policy.yml`,
  `security/policies/container-policy.yml`, and
  `security/policies/release-security-policy.yml`.
- Scanner configs: `security/gitleaks/gitleaks.toml`,
  `security/semgrep/rules.yml`, and `security/trivy/trivy.yaml`.
- Scripts: `scripts/generate-sbom.sh`, `scripts/run-dependency-audit.sh`,
  `scripts/scan-container.sh`, and `scripts/security-release-gate.ts`.
- CI workflow: `.github/workflows/security-gates.yml`.
- Docker hardening: API, worker, and web images run as non-root users and have
  deterministic local image names for scanning.
- Security tests: Python smoke under `tests/security/test_authentication.py`
  plus Playwright specs under `tests/security/specs/`.

Primary commands:

- `make security`: secrets, SAST, SCA, dependency audit, SBOM, Dockerfile lint.
- `make image-scan`: build and scan local API/worker/web images.
- `make test-security`: pytest security smoke plus Playwright security specs.
- `yarn gate:security`: evaluate required security evidence.

## Phase 5 Release Readiness

- Risk strategy docs:
  `docs/qa-strategy/risk-based-test-strategy.md`,
  `docs/qa-strategy/release-gates.md`,
  `docs/security/security-release-gates.md`, and
  `docs/system-design/release-governance.md`.
- Machine-readable risk model:
  `security/policies/risk-model.yml`.
- Release readiness script:
  `scripts/release-readiness.ts`.
- CI workflow:
  `.github/workflows/release-gates.yml`.
- Primary command:
  `yarn gate:release`.
- Output artifact:
  `reports/release-readiness.json`.

## Phase 6 OCR/Document Validation

- OCR adapter: `apps/worker/worker/ocr/mock.py` supports embedded
  `SECUREDOX-FIXTURE:` JSON blocks for deterministic extraction.
- Manual review fallback: low-confidence but rule-passing documents move to
  `REVIEW_REQUIRED`; reviewer submission moves them to `VALIDATED`.
- Document test sets: `test-documents/{clean,rotated,blurry,low-contrast,missing-field,duplicate,invalid-format,malicious}`.
- Expected OCR outputs: `tests/fixtures/ocr/*.expected.json`.
- OCR tests: `tests/ocr/test_ocr_validation.py`.
- OCR quality evidence: `tests/reports/ocr-quality-summary.json`.
- Release readiness consumes `reports/junit-ocr.xml` and OCR quality evidence.

## Phase 7 API, DB, and Contract Testing

- API runtime additions: `GET /api/v1/audit-logs` is tenant-scoped, and
  `PATCH /api/v1/documents/{id}/review` validates reviewer review payloads.
- Duplicate reviewer submission is blocked by checking for an existing
  `DOCUMENT_SUBMITTED` audit event.
- Python API boundary tests: `tests/api/test_document_boundaries.py`.
- Python DB integrity tests: `tests/db/test_integrity_boundaries.py`.
- Python helpers now expose raw response methods for authz/negative API tests,
  audit log listing, checksum lookup, extracted fields, and validation results.
- Contract suite: `tests/contract/document-api.consumer.test.ts`,
  `tests/contract/document-api.provider.test.ts`, and
  `tests/contract/contracts/document-api.pact.json`.
- Contract evidence command: `yarn test:contract`, wired through
  `make test-contract` and `.github/workflows/release-gates.yml`.
- Release readiness consumes contract evidence from `reports/junit-contract.xml`
  alongside API and DB JUnit reports.

## Phase 8 Observability and SRE Workflows

- Structured logs: `apps/api/app/core/logging.py` injects
  `correlation_id`, `tenant_id`, `user_id`, `document_id`, `job_id`,
  `service_name`, `event_type`, `status`, `latency_ms`, and `error_code` from
  context variables.
- API request context and metrics: `apps/api/app/observability/middleware.py`.
- Worker job context and metrics: `apps/worker/worker/main.py` and
  `apps/worker/worker/processor.py`.
- Metric definitions: `packages/observability/python/securedox_observability/metrics.py`.
- Prometheus config and alerts: `observability/prometheus/`.
- Grafana dashboards and provisioning: `observability/grafana/`.
- SRE runbooks: `docs/sre-runbooks/`.
- Observability/failure-injection asset tests:
  `tests/observability/test_sre_assets.py`.
- Primary command: `make test-observability`.
- Local observability URLs: Prometheus `http://localhost:9090`, Grafana
  `http://localhost:3001`.

## Phase 9 MCP / AI TestOps Layer

- MCP package: `apps/mcp-test-architect`.
- Local server command: `make mcp-test-architect` or
  `yarn workspace @securedox/mcp-test-architect start`.
- Tool smoke command: `make test-mcp`.
- MCP tools:
  `analyze_route_risk`, `generate_playwright_test`,
  `review_test_for_false_confidence`, `suggest_missing_assertions`,
  `map_test_to_requirement`, `summarize_release_risk`,
  `detect_changed_routes`, `detect_changed_api_contracts`,
  `detect_changed_db_schema`, `detect_changed_security_sensitive_files`,
  `suggest_impacted_tests`, and `suggest_required_release_gates`.
- MCP activity log: `reports/mcp-activity.log` with code/test bodies
  redacted.
- AI-generated-test checklist:
  `docs/qa-strategy/ai-generated-test-review-checklist.md`.
- MCP security policy:
  `security/policies/mcp-test-architect-policy.yml`.
- Generated-test review manifest example:
  `apps/mcp-test-architect/templates/generated-test-review.example.json`.
