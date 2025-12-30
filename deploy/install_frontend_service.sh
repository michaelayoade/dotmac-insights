#!/usr/bin/env bash
set -euo pipefail

# Install the frontend systemd unit and start it.
# Run as a user with sudo privileges:
#   sudo ./deploy/install_frontend_service.sh

SERVICE_SRC=deploy/systemd/frontend.service
SERVICE_DST=/etc/systemd/system/frontend.service
DEV_SCRIPT_SRC=deploy/start-frontend-dev.sh
DEV_SCRIPT_DST=/usr/local/bin/start-frontend-dev.sh

echo "Installing frontend service..."

# Copy service unit
sudo cp "$SERVICE_SRC" "$SERVICE_DST"
sudo chown root:root "$SERVICE_DST"

# Copy dev helper script
sudo cp "$DEV_SCRIPT_SRC" "$DEV_SCRIPT_DST"
sudo chown root:root "$DEV_SCRIPT_DST"
sudo chmod +x "$DEV_SCRIPT_DST"

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable --now frontend.service

# Show status
sudo systemctl status frontend.service --no-pager

cat <<'EOF'

Installed and started frontend.service.
If the service fails to start, check the journal:
  sudo journalctl -u frontend.service -f

Notes:
- Ensure /etc/dotmac-insights/frontend.env exists and has simple KEY=VALUE lines (no inline comments).
- If you use nvm or non-standard node installs, either:
  * install Node/npm system-wide (recommended for systemd services), or
  * add an absolute PATH to the unit (Environment=PATH=/home/dotmac3/.nvm/versions/node/...), or
  * update the unit to source a profile file that loads nvm.

EOF
