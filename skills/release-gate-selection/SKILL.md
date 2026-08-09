---
name: release-gate-selection
description: Use this skill to choose SecureDox release gates, explain blocking versus warning gates, and summarize go/no-go evidence for changed files.
---

# Release Gate Selection

Use this skill when a PR or agent-generated change needs gate selection.

## Workflow

1. Run `node --experimental-strip-types scripts/agents/release-gate-selector.ts`.
2. Compare required gates to available evidence in `reports/`.
3. Treat missing P0 evidence as a blocker.
4. Explain which failures block release and which are warnings.
5. Finish with `yarn gate:release` when evidence is available.

## Gate Hints

- Security-sensitive changes require security gates.
- API contract changes require contract tests.
- DB schema changes require DB tests.
- OCR/worker changes require OCR and observability checks.
