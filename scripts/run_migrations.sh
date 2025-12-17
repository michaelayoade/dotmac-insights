#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required to run migrations" >&2
  exit 1
fi

if [[ "${DATABASE_URL}" == sqlite* ]]; then
  echo "Refusing to run migrations against sqlite in production" >&2
  exit 1
fi

poetry run alembic upgrade head
