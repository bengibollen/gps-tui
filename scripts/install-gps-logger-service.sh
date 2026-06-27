#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_TEMPLATE="${PROJECT_DIR}/systemd/gps-tui-logger.service"
UNIT_PATH="/etc/systemd/system/gps-tui-logger.service"
ENV_PATH="/etc/default/gps-tui-logger"
LOG_DIR="${GPS_LOG_DIR:-/var/log/gps}"

if [[ ! -f "${UNIT_TEMPLATE}" ]]; then
  echo "Missing unit template: ${UNIT_TEMPLATE}" >&2
  exit 1
fi

sudo mkdir -p "${LOG_DIR}"

if [[ ! -f "${ENV_PATH}" ]]; then
  sudo tee "${ENV_PATH}" >/dev/null <<EOF
GPSD_HOST=localhost
GPSD_PORT=2947
GPS_LOG_DIR=${LOG_DIR}
GPS_LOG_INTERVAL=1
EOF
fi

sed "s#__PROJECT_DIR__#${PROJECT_DIR}#g" "${UNIT_TEMPLATE}" | sudo tee "${UNIT_PATH}" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable gps-tui-logger.service

echo "Installed gps-tui-logger.service"
echo "Config: ${ENV_PATH}"
echo "Log dir: ${LOG_DIR}"
echo
echo "Start now with:"
echo "  sudo systemctl start gps-tui-logger.service"
echo
echo "Check status with:"
echo "  systemctl status gps-tui-logger.service"
