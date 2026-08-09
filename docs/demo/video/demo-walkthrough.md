# Demo Video Walkthrough

This is the script for a 6 to 8 minute recorded demo.

## 0:00 to 0:45: Project Frame

Show `README.md` and `docs/START-HERE-FOR-REVIEWERS.md`.

Message: SecureDox is a regulated document-intake app built to demonstrate
senior SDET, DevSecOps, SRE, and AI TestOps judgment.

## 0:45 to 2:00: Runtime

Start the stack:

```bash
make up
```

Show:

- Web app at `http://localhost:3000`
- API readiness at `http://localhost:8000/ready`
- Nginx gateway at `http://localhost:8080`

## 2:00 to 3:30: Critical Workflow

Upload a fixture document, wait for OCR processing, review fields, submit, and
show audit events.

## 3:30 to 4:45: Test Architecture

Run or show evidence for:

- API tests
- DB integrity tests
- Security tests
- OCR tests
- Contract tests
- Release readiness

## 4:45 to 5:45: DevSecOps and SRE

Show security gates, SBOM, Nginx hardening, Prometheus, Grafana dashboards, and
SRE runbooks.

## 5:45 to 7:00: MCP and Agent Helpers

Run:

```bash
yarn agents:impacted-tests --file apps/api/app/api/v1/documents.py
yarn workspace @securedox/mcp-test-architect list-tools
```

Explain that AI-generated tests are drafts until human review approves them.

## Close

Open `docs/recruiter/resume-bullets.md` and summarize the hiring signal.
