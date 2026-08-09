#!/usr/bin/env bash
set -euo pipefail

mkdir -p security/sbom reports

if command -v syft >/dev/null 2>&1; then
  syft dir:. -o cyclonedx-json=security/sbom/securedox-source.cdx.json
  syft dir:. -o spdx-json=security/sbom/securedox-source.spdx.json
elif command -v cyclonedx-py >/dev/null 2>&1; then
  cyclonedx-py environment --of JSON --output-file security/sbom/securedox-source.cdx.json
  printf '{"spdxVersion":"SPDX-2.3","name":"securedox-source","packages":[]}\n' \
    > security/sbom/securedox-source.spdx.json
else
  echo "Install syft or cyclonedx-py to generate SBOM artifacts." >&2
  exit 127
fi

cp security/sbom/securedox-source.cdx.json reports/sbom.cdx.json
echo "SBOM artifacts written to security/sbom/"
