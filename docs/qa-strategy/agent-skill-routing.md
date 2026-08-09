# Agent and Skill Routing

SecureDox uses two related layers:

- `agents/`: human-readable agent briefs, responsibilities, and examples.
- `.codex/agents/`: project-scoped Codex custom subagent runtime configs.
- `skills/`: reusable task instructions that Codex can load when available.

## How Subagents Are Used

Ask Codex to delegate parallel review when work can be split cleanly:

```text
Review this branch with subagents. Use security-reviewer for auth and upload
risks, test-architect for missing test coverage, contract-test-reviewer for API
shape changes, and release-gate-analyst for required gates. Wait for all agents
and summarize blockers first.
```

Use subagents for read-heavy review, risk mapping, evidence checks, and
triage. Keep implementation in the main thread or a single focused worker to
avoid edit conflicts.

## Routing Table

| Change or task | Subagent | Skill | Helper command |
| --- | --- | --- | --- |
| Broad PR or release review | `qa-architect` | `agent-loop-kit` | `yarn agents:impacted-tests` |
| Test scope or missing coverage | `test-architect` | `test-impact-analysis` | `yarn agents:impacted-tests` |
| AI-generated test review | `test-architect` | `false-confidence-review` | `yarn test:agents` |
| Auth, authorization, IDOR, uploads | `security-reviewer` | `security-impact-review` | `node --experimental-strip-types scripts/agents/security-impact-check.ts` |
| Dependency, Docker, IaC, CI security | `security-reviewer` | `security-impact-review` | `yarn agents:release-gates` |
| Release go/no-go evidence | `release-gate-analyst` | `release-gate-selection` | `yarn gate:release` |
| API response or Pact shape | `contract-test-reviewer` | `test-impact-analysis` | `node --experimental-strip-types scripts/agents/api-contract-diff.ts` |
| DB schema or persisted state risk | `test-architect` | `test-impact-analysis` | `node --experimental-strip-types scripts/agents/db-schema-diff.ts` |
| Logs, metrics, dashboards, alerts | `observability-reviewer` | `agent-loop-kit` | `node --experimental-strip-types scripts/agents/observability-impact-check.ts` |
| Flaky failure triage | `flaky-test-triage` | `anti-slop-patterns` | `yarn check:flake` |
| README, diagrams, runbooks, strategy | `documentation-maintainer` | `anti-slop-patterns` | `yarn agents:changed-files` |

## Skill Pickup Rules

Skills are available only when the Codex environment registers them. This repo
does that in `.codex/config.toml` with `[[skills.config]]` entries pointing to
each local `SKILL.md`.

The `name` and `description` frontmatter are the trigger surface. Keep them
specific enough that the model can choose the right skill without reading every
file. The full `SKILL.md` body is loaded only after a skill is selected.

## Validation

Run:

```bash
yarn agents:validate-assets
```

This checks that:

- each specialist in `agents/` has `prompt.md`, `responsibilities.md`, and
  `examples.md`
- each `.codex/agents/*.toml` file has required runtime fields
- each skill has a valid `SKILL.md`
- skill frontmatter uses only `name` and `description`
- copied scaffold files and `.DS_Store` files are absent
