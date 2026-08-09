# AI-Generated Test Review Checklist

AI-generated tests are drafts. They may speed up coverage discovery, but they do
not become release evidence until a human reviewer approves them.

## Required Review

Before merge, confirm:

- Does the test assert the business outcome?
- Does it validate persisted state when data is written?
- Does it check negative paths?
- Does it prove auth or authorization behavior?
- Does it avoid only checking visible text?
- Does it fail before the bug is fixed?
- Does it use deterministic test data?
- Does it check audit logs when required?
- Does it avoid over-mocking the real risk?

## False-Confidence Signals

Treat the generated test as weak when it:

- Asserts only text, CSS, or a success toast.
- Uses random data without deterministic suffixes or fixture factories.
- Mocks the API, DB, worker, or auth boundary that the risk actually depends on.
- Has no negative path for validation, tenant isolation, or duplicate actions.
- Never checks audit logs for regulated workflow transitions.
- Would pass if the backend silently failed to persist state.

## Approval Evidence

Generated tests must be listed in `tests/reports/generated-test-review.json`
when they are used as release evidence:

```json
{
  "tests": [
    {
      "test": "tests/e2e/specs/example.generated.spec.ts",
      "requirement": "REQ-DOC-UPLOAD",
      "approved": true,
      "reviewer": "human-reviewer",
      "notes": "Business, DB, authz, and audit assertions verified."
    }
  ]
}
```

`scripts/release-readiness.ts` blocks release when a generated test entry is
present with `approved: false`.

## MCP Workflow

1. Ask the MCP Test Architect for impacted tests or a draft test.
2. Run `review_test_for_false_confidence` against the draft.
3. Add missing assertions before committing the test.
4. Map the test to a requirement with `map_test_to_requirement`.
5. Add or update the generated-test review manifest.
6. Run the relevant impacted tests and `yarn gate:release`.
