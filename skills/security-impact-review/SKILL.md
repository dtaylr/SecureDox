---
name: security-impact-review
description: Use this skill to review SecureDox changes for authentication, authorization, upload validation, sensitive logging, dependencies, Dockerfiles, IaC, and OWASP-mapped tests.
---

# Security Impact Review

Use this skill when changed files touch auth, tenant isolation, document access,
uploads, OCR inputs, security policies, dependencies, Dockerfiles, CI, IaC, or
logging.

## Workflow

1. Run `node --experimental-strip-types scripts/agents/security-impact-check.ts`.
2. If API routes changed, run
   `node --experimental-strip-types scripts/agents/route-map.ts`.
3. Require IDOR and unauthenticated tests for object-level access changes.
4. Require upload-validation tests for document intake changes.
5. Require secret scanning, SAST, SCA, SBOM, Dockerfile lint, and container scan
   evidence for security-sensitive, dependency, or Docker changes.
6. Check release impact with
   `node --experimental-strip-types scripts/agents/release-gate-selector.ts`.

## Review Focus

- Mocked auth cannot bypass tenant boundaries.
- `GET /documents/:id`, review, submit, and audit-log reads enforce ownership.
- Upload gates reject malformed, duplicate, oversized, malicious, or unsupported
  documents safely.
- Error responses do not reveal another tenant's records.
- Structured logs redact PII and secrets while preserving correlation IDs.
- Docker, Compose, Kubernetes, Terraform, and Ansible changes preserve least
  privilege defaults.
- Dependency changes generate updated vulnerability and SBOM evidence.

## Output

Return:

- risk level
- affected assets and trust boundaries
- required security tests
- required security gates
- sensitive logging concerns
- release blockers or manual-review items
