#!/usr/bin/env bash
# NAS: install iot-scheduler systemd timer (1분마다 docker exec scheduler)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
UNIT_DIR="${ROOT}/infra/systemd"
DEST="/etc/systemd/system"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

install -m 644 "${UNIT_DIR}/iot-scheduler.service" "${DEST}/iot-scheduler.service"
install -m 644 "${UNIT_DIR}/iot-scheduler.timer" "${DEST}/iot-scheduler.timer"

systemctl daemon-reload
systemctl enable --now iot-scheduler.timer
systemctl list-timers iot-scheduler.timer --no-pager

echo "OK — iot-scheduler.timer active"
