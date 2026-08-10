SHELL := /bin/bash
COMPOSE := docker compose -f infra/docker/docker-compose.yml --env-file .env
PY := .venv/bin/python
PIP := .venv/bin/pip

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------
.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_.-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}'

.PHONY: bootstrap
bootstrap: .env venv node-deps ## One-time local setup (env file, venv, node deps)
	@echo "Bootstrap complete. Next: make up && make migrate && make seed"

.env:
	cp .env.example .env
	@echo "Created .env from template."

.PHONY: venv
venv: ## Create the Python venv and install api + worker + test deps
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e packages/shared/python -e packages/observability/python
	$(PIP) install -r apps/api/requirements-dev.txt
	$(PIP) install -r apps/worker/requirements-dev.txt
	$(PIP) install -r tests/requirements.txt

.PHONY: node-deps
node-deps: ## Install JS/TS workspace deps
	yarn install

# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------
.PHONY: up
up: ## Start the full local stack
	$(COMPOSE) up -d --build

.PHONY: up-core
up-core: ## Start app services only (no prometheus/grafana)
	$(COMPOSE) up -d --build postgres redis api worker web nginx

.PHONY: down
down: ## Stop the stack and drop volumes
	$(COMPOSE) down -v --remove-orphans

.PHONY: restart
restart: down up ## Recreate the stack from scratch

.PHONY: logs
logs: ## Tail all service logs
	$(COMPOSE) logs -f --tail=100

.PHONY: ps
ps: ## Show container status
	$(COMPOSE) ps

.PHONY: migrate
migrate: ## Apply Alembic migrations
	$(COMPOSE) exec api alembic upgrade head

.PHONY: revision
revision: ## Autogenerate a migration: make revision M="add x"
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(M)"

.PHONY: seed
seed: ## Load demo tenants, rule sets and sample documents
	$(COMPOSE) exec api python -m app.db.seed

.PHONY: psql
psql: ## Open a psql shell
	$(COMPOSE) exec postgres psql -U securedox -d securedox

# ---------------------------------------------------------------------------
# Test pyramid
# ---------------------------------------------------------------------------
.PHONY: test
test: test-unit test-api test-db test-security test-ocr test-contract test-observability test-mcp test-agents test-platform ## Fast suites run on every commit

.PHONY: test-unit
test-unit: ## Service unit tests (api + worker)
	$(PY) -m pytest apps/api/tests apps/worker/tests -m "not integration" \
	  --cov=apps/api/app --cov=apps/worker/worker \
	  --cov-report=xml:reports/coverage-unit.xml --cov-report=term-missing

.PHONY: test-api
test-api: ## API functional tests against the running stack
	$(PY) -m pytest tests/api -v --junitxml=reports/junit-api.xml

.PHONY: test-db
test-db: ## Database rule/constraint/integrity validation
	$(PY) -m pytest tests/db -v --junitxml=reports/junit-db.xml

.PHONY: test-security
test-security: ## Security smoke tests against the running stack
	$(PY) -m pytest tests/security -v --junitxml=reports/junit-security.xml
	yarn test:security

.PHONY: test-contract
test-contract: ## Provider + consumer contract verification
	yarn test:contract

.PHONY: test-observability
test-observability: ## SRE asset and observability contract tests
	$(PY) -m pytest tests/observability -v --junitxml=reports/junit-observability.xml

.PHONY: test-mcp
test-mcp: ## MCP Test Architect tool smoke tests
	yarn test:mcp

.PHONY: test-agents
test-agents: ## Agent helper classifier and asset validation tests
	yarn test:agents

.PHONY: mcp-test-architect
mcp-test-architect: ## Start the local MCP Test Architect server over stdio
	yarn mcp:test-architect

.PHONY: test-e2e
test-e2e: ## Playwright end-to-end specs
	yarn test:e2e

.PHONY: test-smoke
test-smoke: test-api test-db test-security test-ocr test-e2e ## Critical phase-3 smoke suite

.PHONY: test-ocr
test-ocr: ## OCR/document validation workflow tests
	$(PY) -m pytest tests/ocr -v --junitxml=reports/junit-ocr.xml

.PHONY: test-bdd
test-bdd: ## Cucumber feature files driven by Playwright
	yarn test:bdd

.PHONY: test-mobile-api
test-mobile-api: ## Mobile-specific API contract, pagination and offline-sync tests
	$(PY) -m pytest tests/mobile-api -v --junitxml=reports/junit-mobile-api.xml

.PHONY: test-mobile-ui
test-mobile-ui: ## Appium mobile UI suite (requires an emulator/simulator or device farm)
	yarn test:mobile:ui

.PHONY: test-arch
test-arch: ## Architecture fitness functions (layering, import boundaries)
	yarn test:arch
	$(PY) -m lint_imports --config tests/architecture/importlinter.ini

.PHONY: test-platform
test-platform: ## Platform/IaC architecture asset tests
	$(PY) -m pytest tests/architecture -v --junitxml=reports/junit-architecture.xml

.PHONY: test-perf
test-perf: ## k6 smoke + load profiles
	./scripts/run-performance.sh smoke

.PHONY: test-chaos
test-chaos: ## Fault-injection scenarios against the local stack
	./tests/chaos/run-scenarios.sh

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
.PHONY: security
security: secrets sast sca dep-audit sbom dockerfile-lint ## Static security suite (no running app required)

.PHONY: sast
sast: ## Semgrep static analysis
	mkdir -p reports
	semgrep scan --config security/semgrep/rules.yml \
	  --sarif --output reports/semgrep.sarif --error

.PHONY: sca
sca: ## Dependency vulnerability scan
	mkdir -p reports
	trivy fs --config security/trivy/trivy.yaml --scanners vuln,license \
	  --format json --output reports/trivy-fs.json .

.PHONY: dep-audit
dep-audit: ## npm/yarn/OSV dependency audit
	./scripts/run-dependency-audit.sh

.PHONY: secrets
secrets: ## Secret scanning
	mkdir -p reports
	gitleaks detect --config security/gitleaks/gitleaks.toml \
	  --report-format sarif --report-path reports/gitleaks.sarif

.PHONY: sbom
sbom: ## Generate CycloneDX SBOMs for every artifact
	./scripts/generate-sbom.sh

.PHONY: iac-scan
iac-scan: ## Terraform / Dockerfile / K8s misconfiguration scan
	mkdir -p reports
	trivy config --config security/trivy/trivy.yaml --format json \
	  --output reports/trivy-config.json infra/

.PHONY: checkov
checkov: ## Checkov scan for Terraform/Kubernetes/Compose/Ansible
	mkdir -p reports
	checkov -d infra --quiet --output json --output-file-path reports/checkov.json

.PHONY: terraform-fmt
terraform-fmt: ## Check Terraform formatting
	terraform -chdir=infra/terraform fmt -recursive -check

.PHONY: terraform-validate
terraform-validate: ## Validate local and staging Terraform modules
	terraform -chdir=infra/terraform/envs/local init -backend=false
	terraform -chdir=infra/terraform/envs/local validate
	terraform -chdir=infra/terraform/envs/staging init -backend=false
	terraform -chdir=infra/terraform/envs/staging validate

.PHONY: ansible-check
ansible-check: ## Ansible syntax checks
	ansible-playbook -i infra/ansible/inventories/local.ini infra/ansible/playbooks/site.yml --syntax-check
	ansible-playbook -i infra/ansible/inventories/local.ini infra/ansible/playbooks/check.yml --syntax-check

.PHONY: kube-validate
kube-validate: ## Kubernetes client-side manifest validation
	kubectl apply -k infra/k8s/minikube/base --dry-run=client

.PHONY: dockerfile-lint
dockerfile-lint: ## Lint Dockerfiles with Hadolint
	hadolint apps/api/Dockerfile apps/worker/Dockerfile apps/web/Dockerfile

.PHONY: image-scan
image-scan: ## Scan built container images
	./scripts/scan-container.sh

.PHONY: dast
dast: ## OWASP ZAP baseline against the running API
	./scripts/run-zap-baseline.sh

# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------
.PHONY: gate-security
gate-security: ## Evaluate the security release policy against scan reports
	yarn gate:security

.PHONY: gate-release
gate-release: ## Evaluate the release-readiness scorecard
	yarn gate:release

.PHONY: lint
lint: ## Lint everything
	yarn lint
	$(PY) -m ruff check apps packages tests scripts
	$(PY) -m ruff format --check apps packages tests
	$(PY) -m mypy apps/api/app apps/worker/worker

.PHONY: fmt
fmt: ## Autoformat everything
	yarn format
	$(PY) -m ruff format apps packages tests
	$(PY) -m ruff check --fix apps packages tests

.PHONY: hooks
hooks: ## Install pre-commit hooks
	pre-commit install --install-hooks --hook-type pre-commit --hook-type commit-msg
