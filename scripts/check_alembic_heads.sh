#!/usr/bin/env bash
set -euo pipefail

ALLOW_MULTIPLE_HEADS="${ALLOW_MULTIPLE_HEADS:-}"

heads_output=$(poetry run alembic heads)
head_count=$(printf "%s\n" "${heads_output}" | grep -E "\(head\)" -c || true)

if [[ -n "${ALLOW_MULTIPLE_HEADS}" ]]; then
  echo "ALLOW_MULTIPLE_HEADS is set; skipping head check."
  exit 0
fi

if [[ "${head_count}" -ne 1 ]]; then
  echo "Expected a single Alembic head, found ${head_count}."
  echo ""
  echo "${heads_output}"
  echo ""
  echo "Resolve by merging heads or specifying a branch head."
  exit 1
fi

echo "Alembic head check passed."
