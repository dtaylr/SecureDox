# Security Gates

Phase 4 makes security checks part of normal development.

## Local Commands

```bash
make hooks
make security
make image-scan
make test-security
yarn gate:security
```

## Evidence

- `reports/gitleaks.sarif`
- `reports/semgrep.sarif`
- `reports/trivy-fs.json`
- `reports/trivy-images.json`
- `security/sbom/securedox-source.cdx.json`
- `security/sbom/securedox-source.spdx.json`

## Policies

- `security/policies/dependency-policy.yml`
- `security/policies/container-policy.yml`
- `security/policies/release-security-policy.yml`

OWASP ZAP baseline is intentionally deferred to Phase 5 or 6.
