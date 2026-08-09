# Secret Detected In CI

Alert Source: security CI and release gate blockers

## Signals

- Gitleaks report contains one or more findings.
- Release readiness includes `secret finding(s) detected`.
- `release_gate_failures_total{gate="security"}` is emitted in release evidence.

## Triage

1. Open `reports/gitleaks.sarif`.
2. Identify file path, commit, and detector type.
3. Determine whether the value is a real secret, test fixture, or documented allowlist candidate.
4. If real, assume compromise and rotate before removing the finding.

## Mitigation

- Revoke and rotate real credentials.
- Remove the secret from the working tree and history as required by policy.
- Add a narrow allowlist only for non-secret deterministic fixtures.

## Verification

- Gitleaks passes.
- Release readiness no longer reports secret blockers.
- Security reviewer records approval for any allowlist.

## Failure Injection Drill

Create a local throwaway file containing a fake high-entropy token and run the secret scan. Confirm the pre-commit hook and CI gate block it. Remove the file before committing.
