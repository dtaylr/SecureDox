# Security Release Gates

Security gates are release blockers, not informational dashboards.

## Required Evidence

| Evidence | Source | Blocks On |
| --- | --- | --- |
| Secret scan | `reports/gitleaks.sarif` | Any finding |
| SAST | `reports/semgrep.sarif` | Any ERROR-level blocker |
| Dependency scan | `reports/trivy-fs.json` | Any critical vulnerability |
| Container scan | `reports/trivy-images.json` | Any critical vulnerability |
| SBOM | `security/sbom/securedox-source.cdx.json`, `security/sbom/securedox-source.spdx.json` | Missing file |
| IDOR tests | `tests/reports/security-playwright-results.json` | Missing/failing IDOR spec |
| Log redaction tests | `tests/reports/security-playwright-results.json` | Missing/failing redaction spec |
| Upload validation tests | `tests/reports/security-playwright-results.json` | Missing/failing upload validation spec |

## Policy Files

- `security/policies/dependency-policy.yml`
- `security/policies/container-policy.yml`
- `security/policies/release-security-policy.yml`
- `security/gitleaks/gitleaks.toml`
- `security/semgrep/rules.yml`
- `security/trivy/trivy.yaml`

## Failure Examples

- A leaked token appears in a commit.
- A tenant can read another tenant's document.
- A document parser exception leaks raw document content.
- A critical container vulnerability is present.
- SBOM generation fails.

Every exception requires a ticket, owner, expiry, and compensating control.
