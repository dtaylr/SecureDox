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
