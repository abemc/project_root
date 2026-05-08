Deployment samples for Project Analyzer collector

1) systemd

- Copy the example env file to `/etc/project_analyzer/collector.env` and edit values:

  sudo mkdir -p /etc/project_analyzer
  sudo cp deploy/collector.env.example /etc/project_analyzer/collector.env
  sudo vim /etc/project_analyzer/collector.env

- Copy unit file and enable service:

  sudo cp deploy/collector.service /etc/systemd/system/project-analyzer-collector.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now project-analyzer-collector.service

- Logs are written to the path configured in `LOG_PATH` (default `/var/log/project_analyzer/central.log`). Ensure directory exists and is writable by the service user.

2) Docker Compose

- Copy TLS certs into `deploy/certs/` or mount your own certs directory. Provide `COLLECTOR_SECRET` via environment or `.env` file.

- Example run:

  COLLECTOR_SECRET=mysecret docker compose -f deploy/docker-compose-collector.yml up -d

- The compose file includes a healthcheck that verifies the collector port is listening.

Security notes

- For production, use a proper CA-signed certificate and restrict access via firewall or API gateway.
- Consider running the collector behind a reverse proxy (nginx) for TLS termination and rate limiting.
