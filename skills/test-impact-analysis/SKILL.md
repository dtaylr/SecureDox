---
name: test-impact-analysis
description: Use this skill to classify SecureDox code changes, select impacted tests, map tests to risk, and avoid over-testing low-risk changes.
---

# Test Impact Analysis

Use this skill when a change needs QA scope, impacted test selection, or risk
mapping.

## Workflow

1. Run `node --experimental-strip-types scripts/agents/changed-files.ts`.
2. Run `node --experimental-strip-types scripts/agents/impacted-tests.ts`.
3. For API routes, run `node --experimental-strip-types scripts/agents/route-map.ts`.
4. Recommend the smallest set of tests that proves the business risk.
5. Flag missing negative paths, authz checks, DB checks, and audit assertions.

## Rules

- P0/P1 changes need release-readiness evidence.
- API contract changes need API and contract tests.
- DB schema changes need DB integrity tests.
- Document workflow changes usually need audit-log assertions.
- Do not suggest broad E2E coverage for docs-only or low-risk UI copy changes.
