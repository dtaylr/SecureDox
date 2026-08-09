---
name: false-confidence-review
description: Use this skill to review AI-generated SecureDox tests for weak assertions, over-mocking, missing negative paths, missing audit checks, and missing human approval.
---

# False Confidence Review

Use this skill when reviewing AI-generated tests or test suggestions.

## Workflow

1. Run MCP tool `review_test_for_false_confidence` when available.
2. Check `docs/qa-strategy/ai-generated-test-review-checklist.md`.
3. Require generated tests to be represented in
   `tests/reports/generated-test-review.json` when they count as release
   evidence.
4. Do not approve tests that only check visible text, over-mock the boundary,
   or omit negative/authz/audit assertions for regulated workflows.

## Merge Rule

Generated tests are drafts until a human reviewer marks them approved. Release
readiness blocks unapproved generated-test manifest entries.
