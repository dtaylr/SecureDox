# Local Runtime

Phase 2 runs a small document-intake stack: web, API, worker, Postgres, Redis,
shared local document storage, and an nginx gateway.

## Start

```bash
make bootstrap
make up
```

The API container runs migrations and seed data on startup. Re-run seed data
manually when needed:

```bash
make seed
```

## URLs

- Web app: http://localhost:3000
- API health: http://localhost:8000/health
- API readiness: http://localhost:8000/ready
- API docs: http://localhost:8000/docs
- Gateway: http://localhost:8080
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

## Demo Login

All demo users use the password `securedox-demo`.

- `admin`
- `reviewer`
- `uploader`

The default tenant is `acme-lending`. Seed data also creates
`northwind-health`.

## Stop

```bash
make down
```

## Phase 3 Smoke Tests

With the stack running:

```bash
make test-api
make test-db
make test-security
make test-ocr
yarn test:e2e
```

Or run the critical smoke lane:

```bash
make test-smoke
```

## Phase 4 Security Gates

Install hooks once:

```bash
make hooks
```

Run static security gates:

```bash
make security
```

Run image scanning after Docker is available:

```bash
make image-scan
```

Security evidence is written under `reports/` and `security/sbom/`.

## Phase 5 Release Readiness

Generate a go/no-go decision from available evidence:

```bash
yarn gate:release
```

The script writes `reports/release-readiness.json` and exits non-zero when the
decision is `NO-GO`. It also writes Prometheus text evidence to
`reports/release-readiness.prom`.

## Phase 8 Observability

Prometheus scrapes:

- API metrics: `api:8000/metrics`
- Worker metrics: `worker:9100/metrics`

Grafana loads dashboards from `observability/grafana/dashboards`. Local login
defaults to `admin` / `securedox`.

Run SRE asset checks:

```bash
make test-observability
```

Runbooks live under `docs/sre-runbooks/`, and alert rules in
`observability/prometheus/alerts.yml` link back to them.

## Phase 9 MCP Test Architect

Start the local MCP server over stdio:

```bash
make mcp-test-architect
```

List available MCP tools without starting a client session:

```bash
yarn workspace @securedox/mcp-test-architect list-tools
```

Run MCP tool smoke tests:

```bash
make test-mcp
```

Generated tests require human review before merge. Use
`docs/qa-strategy/ai-generated-test-review-checklist.md` and record approvals
in `tests/reports/generated-test-review.json` when generated tests are used as
release evidence.

## Phase 10 Agents and Helper Scripts

Agent prompts live under `agents/`, with one folder per specialist. Repo-local
skills live under `skills/`.

Run helper classifiers:

```bash
yarn agents:changed-files
yarn agents:impacted-tests
yarn agents:release-gates
yarn agents:validate-assets
make test-agents
```

The helper CLIs accept explicit files, for example:

```bash
node --experimental-strip-types scripts/agents/impacted-tests.ts \
  --file apps/api/app/api/v1/documents.py \
  --file apps/api/app/core/security.py
```

Agent folders must contain `prompt.md`, `responsibilities.md`, and
`examples.md`. Runtime subagents live in `.codex/agents/*.toml`. Skill folders
must contain a lean `SKILL.md` with only `name` and `description` frontmatter.
`yarn agents:validate-assets` fails on missing runtime agent configs, copied
scaffold files, nested agent-kit bundles, missing skill files, or `.DS_Store`
drift.

The full routing model is documented in
`docs/qa-strategy/agent-skill-routing.md`.

## Phase 11 Platform

Platform checks:

```bash
make terraform-validate
make ansible-check
make kube-validate
make iac-scan
make checkov
make test-platform
```

Key paths:

- Nginx: `infra/docker/nginx.conf`
- Terraform: `infra/terraform`
- Ansible: `infra/ansible`
- Minikube: `infra/k8s/minikube`
- Platform docs: `docs/system-design/platform-infrastructure.md`

## Phase 12 Reviewer Polish

Start with:

```text
README.md
docs/START-HERE-FOR-REVIEWERS.md
```

Demo assets:

- Screenshots: `docs/demo/screenshots/`
- Demo walkthrough: `docs/demo/video/demo-walkthrough.md`
- Sample reports: `docs/demo/reports/`
- Recruiter copy: `docs/recruiter/`
