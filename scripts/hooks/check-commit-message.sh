#!/usr/bin/env bash
set -euo pipefail

message_file="${1:?commit message file is required}"
first_line="$(head -n 1 "$message_file")"

if [[ "$first_line" =~ ^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|security)(\([a-z0-9._-]+\))?!?:\ .+ ]]; then
  exit 0
fi

cat >&2 <<'EOF'
Commit message must follow Conventional Commits, for example:
  feat(api): add document review endpoint
  security(ci): add secret scanning gate
EOF
exit 1
