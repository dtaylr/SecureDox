# Examples

## API Review Change

Input: `apps/api/app/api/v1/documents.py`

Output:

```json
{
  "risk": "high",
  "required_checks": ["api-tests", "contract-tests", "e2e-critical", "release-readiness"],
  "recommended_reviewers": ["test-architect", "contract-test-reviewer"]
}
```

## Low-Risk Docs Change

Input: `docs/local-runtime.md`

Output: docs review only; do not run full E2E unless the doc changes commands
that developers depend on.
