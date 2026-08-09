# QA Architect Examples

## Broad PR Review

Input:

```text
Review this branch for release risk.
```

Expected output:

```json
{
  "risk": "high",
  "impacted_workflows": ["document_upload", "ocr_review", "audit_log"],
  "delegate_to": ["test-architect", "security-reviewer", "release-gate-analyst"],
  "required_checks": ["api-tests", "db-tests", "security-authz-tests", "release-readiness"],
  "blockers": ["Upload validation changed without unsafe-file regression evidence"]
}
```

## AI-Generated Test Review

Input:

```text
An AI agent added a Playwright upload test. Decide whether it can count as
release evidence.
```

Expected output:

```json
{
  "risk": "medium",
  "delegate_to": ["test-architect"],
  "required_skill": "false-confidence-review",
  "decision": "does_not_count_yet",
  "missing_evidence": ["DB row assertion", "audit log assertion", "negative upload path"]
}
```

## Release Prep

Input:

```text
Prepare the go/no-go review for this change.
```

Expected output:

```json
{
  "risk": "critical",
  "delegate_to": ["release-gate-analyst", "security-reviewer", "observability-reviewer"],
  "required_checks": ["security-gates", "contract-tests", "observability-tests", "release-readiness"],
  "release_decision_ready": false
}
```
