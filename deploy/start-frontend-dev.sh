#!/usr/bin/env bash
set -euo pipefail

# Dev startup script for systemd: runs Next dev server from the repo
# This script will be executed as the service User (dotmac3 by default).

# Ensure we run from the frontend directory
cd /home/dotmac3/dotmac-insights/frontend

# Make sure npm is available
if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found in PATH. Install Node.js/npm system-wide or adjust the service Environment=PATH to include your node install (or use nvm login hooks)." 1>&2
  exit 1
fi

# Exec the dev server (preserves signals)
exec npm run dev
