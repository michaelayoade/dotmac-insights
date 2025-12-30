#!/usr/bin/env bash
set -euo pipefail

# Optional system-wide env file (clean, without inline comments)
ENV_FILE=/etc/dotmac-insights/frontend.env
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -o allexport
  source "$ENV_FILE"
  set +o allexport
fi

export NODE_ENV=${NODE_ENV:-production}

# Working directory
cd /home/dotmac3/dotmac-insights/frontend

# Ensure dependencies for production
if [ ! -d node_modules ]; then
  npm ci --production
fi

# Build if missing
if [ ! -d .next ]; then
  npm run build
fi

# Run the production start command
exec npm run start
