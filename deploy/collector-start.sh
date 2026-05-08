#!/bin/sh
set -eu
# Source environment file if present
if [ -f /etc/project_analyzer/collector.env ]; then
  # shellcheck disable=SC1091
  . /etc/project_analyzer/collector.env
fi

LOG_PATH=${LOG_PATH:-/var/log/project_analyzer/central.log}

if [ -n "${CERTFILE:-}" ] && [ -n "${KEYFILE:-}" ] && [ -f "${CERTFILE}" ] && [ -f "${KEYFILE}" ]; then
  exec /home/abemc/project_root/.venv/bin/python -m analyzer.collector_cli \
    --path "${LOG_PATH}" --host 0.0.0.0 --port 8443 --auth-secret "${COLLECTOR_SECRET:-}" \
    --certfile "${CERTFILE}" --keyfile "${KEYFILE}"
else
  exec /home/abemc/project_root/.venv/bin/python -m analyzer.collector_cli \
    --path "${LOG_PATH}" --host 0.0.0.0 --port 8443 --auth-secret "${COLLECTOR_SECRET:-}"
fi
