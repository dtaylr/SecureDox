#!/usr/bin/env bash
set -euo pipefail

mkdir -p reports

if command -v osv-scanner >/dev/null 2>&1; then
  osv-scanner --recursive --format json --output reports/osv-scanner.json .
  exit 0
fi

if command -v npm >/dev/null 2>&1 && [[ -f package-lock.json ]]; then
  npm audit --audit-level=high --json > reports/npm-audit.json
  exit 0
fi

if command -v yarn >/dev/null 2>&1; then
  yarn audit --level high --json > reports/yarn-audit.json
  exit 0
fi

cat > reports/dependency-audit-skipped.json <<'JSON'
{
  "status": "skipped",
  "reason": "Install osv-scanner, npm, or yarn to run dependency audit."
}
JSON
echo "No dependency audit tool found; wrote skipped report." >&2
