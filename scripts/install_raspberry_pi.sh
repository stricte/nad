#!/usr/bin/env bash

set -euo pipefail

APP_USER="${APP_USER:-nad}"
APP_GROUP="${APP_GROUP:-nad}"
APP_DIR="${APP_DIR:-/opt/nad}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
SERVICE_NAME="${SERVICE_NAME:-nad-receive.service}"
SYSTEMD_UNIT_PATH="${SYSTEMD_UNIT_PATH:-/etc/systemd/system/$SERVICE_NAME}"
SERIAL_GROUP="${SERIAL_GROUP:-dialout}"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root or via sudo."
    exit 1
fi

install_packages() {
    apt-get update
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-serial \
        git \
        rsync
}

create_user() {
    if ! getent group "${APP_GROUP}" >/dev/null; then
        groupadd --system "${APP_GROUP}"
    fi

    if ! id -u "${APP_USER}" >/dev/null 2>&1; then
        useradd \
            --system \
            --gid "${APP_GROUP}" \
            --create-home \
            --home-dir "/var/lib/${APP_USER}" \
            --shell /usr/sbin/nologin \
            "${APP_USER}"
    fi

    usermod -a -G "${SERIAL_GROUP}" "${APP_USER}"
}

deploy_application() {
    mkdir -p "${APP_DIR}"

    rsync -a \
        --delete \
        --exclude '.git/' \
        --exclude '.codex/' \
        --exclude 'config.py' \
        --exclude '__pycache__/' \
        --exclude 'tests/__pycache__/' \
        --exclude '.pytest_cache/' \
        "${SOURCE_DIR}/" "${APP_DIR}/"

    if [[ ! -f "${APP_DIR}/config.py" && -f "${SOURCE_DIR}/config.py" ]]; then
        cp "${SOURCE_DIR}/config.py" "${APP_DIR}/config.py"
    fi

    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install paho-mqtt pyserial

    chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
}

install_service() {
    cat > "${SYSTEMD_UNIT_PATH}" <<EOF
[Unit]
Description=NAD Receiver Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
SupplementaryGroups=${SERIAL_GROUP}
WorkingDirectory=${APP_DIR}
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/receiver.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
}

print_next_steps() {
    cat <<EOF
Installation complete.

Next steps:
1. Edit ${APP_DIR}/config.py
2. Start with:
   http_ingress_enabled = True
   http_ingress_shadow_mode = True
   volumio_registration_enabled = True
3. Start the service:
   systemctl restart ${SERVICE_NAME}
4. Inspect logs:
   journalctl -u ${SERVICE_NAME} -f
5. Check ingress status:
   curl http://127.0.0.1:8080/ingress/status

Full guide:
${APP_DIR}/docs/raspberry-pi-volumio.md
EOF
}

install_packages
create_user
deploy_application
install_service
print_next_steps
