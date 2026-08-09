#!/usr/bin/env bash
set -euo pipefail

status=0

for file in "$@"; do
  [[ -f "$file" ]] || continue
  if ! grep -qE "Human-Approved: (yes|true)" "$file"; then
    echo "$file: generated test is missing 'Human-Approved: yes' approval marker" >&2
    status=1
  fi
done

exit "$status"
