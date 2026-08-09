#!/usr/bin/env bash
set -euo pipefail

mkdir -p reports

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for container image scanning." >&2
  exit 127
fi
if ! command -v trivy >/dev/null 2>&1; then
  echo "trivy is required for container image scanning." >&2
  exit 127
fi

docker compose -f infra/docker/docker-compose.yml --env-file .env build api worker web

tmp_report="$(mktemp)"
printf '{"SchemaVersion":2,"Results":[]}' > reports/trivy-images.json

for image in securedox/api:local securedox/worker:local securedox/web:local; do
  trivy image \
    --config security/trivy/trivy.yaml \
    --format json \
    --output "$tmp_report" \
    "$image"
  node scripts/security/merge-trivy-reports.mjs reports/trivy-images.json "$tmp_report" "$image"
done

rm -f "$tmp_report"
echo "Container scan report written to reports/trivy-images.json"
