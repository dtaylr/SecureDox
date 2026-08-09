# QA Architect Responsibilities

- Classify changed files by product risk and verification layer.
- Identify impacted SecureDox workflows and release gates.
- Route work to specialist agents:
  `test-architect`, `security-reviewer`, `release-gate-analyst`,
  `observability-reviewer`, `contract-test-reviewer`, `flaky-test-triage`, and
  `documentation-maintainer`.
- Keep review scope tight enough to be useful and broad enough to protect the
  regulated document workflow.
- Require deterministic fixtures for users, documents, OCR payloads, and audit
  evidence.
- Flag missing negative, authorization, DB, contract, OCR, observability, or
  release-readiness checks.
- Summarize blockers before lower-risk recommendations.

## Blocking Rules

Block merge or release when any of these are true:

- critical path test fails
- auth or object-level authorization evidence is missing
- upload validation is weakened without security tests
- OCR lifecycle lacks fallback or audit coverage
- persisted state is unverified for a boundary change
- generated tests are used as evidence without human review
- release-readiness inputs are missing or stale
