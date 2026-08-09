---
name: agent-loop-kit
description: Use this skill to run a disciplined SecureDox agent workflow with scoped context, changed-file classification, impacted-test selection, release-gate evidence, and concise handoff notes.
---

# Agent Loop Kit

Use this skill when coordinating AI-assisted changes in SecureDox, especially
multi-file work, PR review, release preparation, or follow-up implementation
after an agent-generated suggestion.

## Workflow

1. Read `docs/phase2-repo-map.md` before opening broad parts of the repo.
2. Run `node --experimental-strip-types scripts/agents/changed-files.ts`.
3. Run `node --experimental-strip-types scripts/agents/impacted-tests.ts`.
4. Select the smallest relevant reviewer agents from `agents/`.
5. Run the required checks from the impacted-test output.
6. Capture evidence in `reports/` when it contributes to release readiness.

## Agent Rules

- Keep changes scoped to the touched SecureDox workflow.
- Treat auth, authorization, uploads, OCR, audit logs, dependencies, Docker,
  infrastructure, and CI as security-sensitive.
- Generated tests are drafts until reviewed with
  `skills/false-confidence-review`.
- Use deterministic fixtures for users, documents, OCR payloads, and audit
  expectations.
- Do not count a check as release evidence unless it has a machine-readable
  report or a clear command result.

## Handoff Format

Return:

- changed files
- risk level
- required checks
- reviewer agents
- evidence created or missing
- blockers before merge or release
