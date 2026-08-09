---
name: anti-slop-patterns
description: Use this skill to review SecureDox UI, docs, tests, and agent output for generic AI-shaped work, shallow assertions, weak regulated-domain evidence, and repo-inconsistent formatting.
---

# Anti-Slop Patterns

Use this skill when polishing SecureDox output before review, especially for
agent-authored tests, security findings, release reports, diagrams, README
sections, or UI changes.

## Review Priorities

1. Business outcome is explicit.
2. Security and tenant boundaries are proven, not implied.
3. Persisted state and audit evidence are checked where the workflow requires
   it.
4. Copy is specific to document intake, OCR review, release gates, and SDET/SRE
   evidence.
5. The implementation follows existing repo structure and commands.

## Reject These Patterns

- Tests that only check status `200`, visible text, or page load.
- Assertions that stop at the API response when DB state or audit logs are the
  actual risk.
- Security reviews that omit unauthenticated, unauthorized, IDOR, upload
  validation, or log-redaction paths.
- Documentation that uses generic platform language without naming SecureDox
  workflows.
- Agent output that invents tools, paths, reports, metrics, or CI jobs not
  present in the repo.
- Release summaries that hide missing evidence behind optimistic language.

## SecureDox Quality Bar

- Critical document workflows need API, DB, audit, and release-readiness
  evidence.
- OCR changes need confidence, fallback, malformed-file, duplicate-file, and
  lifecycle audit checks.
- Authz changes need object-level ownership tests.
- Observability changes need correlation IDs, metrics, dashboards, alerts, and
  runbook links.
- CI/security changes need clear blocking versus warning behavior.

## Output

Return:

- pass/fail
- shallow or generic patterns found
- exact missing assertions or evidence
- recommended owning agent
- required command or report to prove the fix
