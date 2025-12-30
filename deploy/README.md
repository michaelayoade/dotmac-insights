Systemd service: keep the frontend running

Overview
--------
This repository includes a systemd unit and a small startup script to ensure the frontend (Next.js) runs continuously on a host.

Files added
- `deploy/start-frontend.sh` — idempotent startup script that loads a clean env file, ensures dependencies and build, and execs `npm run start`.
- `deploy/systemd/frontend.service` — systemd unit that runs the script as `dotmac3` and restarts on failure.

Installation (example)
----------------------
1. Create a clean env file for the frontend (systemd `EnvironmentFile`):

   sudo mkdir -p /etc/dotmac-insights
   sudo tee /etc/dotmac-insights/frontend.env > /dev/null <<EOF
   PORT=3000
   NEXT_PUBLIC_API_URL=https://dashboard-api.example.com
   EOF

   Make sure lines are strictly of the form `KEY=VALUE`. Do NOT include inline comments in this file.

2. Copy the unit file and script to the host (already in the repo paths above). On the host:

   sudo cp deploy/systemd/frontend.service /etc/systemd/system/frontend.service
   sudo cp deploy/start-frontend.sh /usr/local/bin/start-frontend.sh
   sudo chown root:root /usr/local/bin/start-frontend.sh
   sudo chmod +x /usr/local/bin/start-frontend.sh

   (Alternatively, keep it in the repo path and adjust `ExecStart` in the unit to the repo path.)

3. Reload systemd and enable/start the service:

   sudo systemctl daemon-reload
   sudo systemctl enable --now frontend.service

4. Check status and logs:

   sudo systemctl status frontend.service
   sudo journalctl -u frontend.service -f

Notes & tips
------------
- The service runs `npm run start` (Next.js production). Ensure you've provided production-ready code (and the environment variables the frontend needs) in `/etc/dotmac-insights/frontend.env`.
- On deploy: run `npm ci` and `npm run build` as part of your deploy pipeline, or allow the service script to build on first start (it already attempts to do so if `.next` is missing).
- Replace `User=dotmac3` with a dedicated system user for production if necessary.
- If you want the frontend to run behind a reverse proxy (recommended), configure nginx/Caddy to proxy to the PORT you set (3000 by default).

If you'd like, I can:
- Create a `sudo`-ready install script that places files in the right locations and enables the service, or
- Add a `systemd` section to the project `Makefile` (with `install-service`, `uninstall-service` targets).

Which would you prefer next?