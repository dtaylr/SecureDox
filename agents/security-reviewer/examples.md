# Examples

## Tenant Boundary Change

If a route fetches documents, require:

- Cross-tenant denial test.
- Unauthenticated request test.
- Audit log redaction check when detail payloads change.

## Dependency Change

If `package.json`, `requirements*.txt`, or `pyproject.toml` changes, require
dependency scan, SBOM generation, and release readiness.
