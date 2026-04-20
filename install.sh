#!/usr/bin/env bash
# install.sh — Install or uninstall the Mender Fleet Simulator as a systemd service.
#
# Usage:
#   sudo ./install.sh              # install (fresh)
#   sudo ./install.sh --update     # update code + service, preserve config and data
#   sudo ./install.sh --uninstall  # remove everything (prompts to decommission devices)
#
# Environment variables (override the defaults shown):
#   INSTALL_DIR     (/opt/mender-simulator)           code + venv
#   DATA_DIR        (/data/mender-simulator)          persistent data (SQLite DB)
#   CONFIG_DIR      ($INSTALL_DIR/config)             configuration files
#   LOG_DIR         (/data/mender-simulator)          log files
#   VENV_DIR        ($INSTALL_DIR/venv)               python virtual environment
#   SERVICE_USER    (mender-simulator)                unix user that runs the service
#   SERVICE_GROUP   ($SERVICE_USER)                   unix group that runs the service
#   SERVICE_FILE    (/etc/systemd/system/mender-simulator.service)
#   PYTHON          (python3)                         python interpreter to use
#   SKIP_DECOMMISSION (0)                             1 = skip remote device decommission
#   ASSUME_YES      (0)                               1 = non-interactive uninstall

set -euo pipefail

# ── Configuration (all overridable via environment) ───────────────────────────
INSTALL_DIR="${INSTALL_DIR:-/opt/mender-simulator}"
DATA_DIR="${DATA_DIR:-/data/mender-simulator}"
CONFIG_DIR="${CONFIG_DIR:-${INSTALL_DIR}/config}"
LOG_DIR="${LOG_DIR:-/data/mender-simulator}"
VENV_DIR="${VENV_DIR:-${INSTALL_DIR}/venv}"
SERVICE_USER="${SERVICE_USER:-mender-simulator}"
SERVICE_GROUP="${SERVICE_GROUP:-${SERVICE_USER}}"
SERVICE_FILE="${SERVICE_FILE:-/etc/systemd/system/mender-simulator.service}"
SERVICE_NAME="$(basename "${SERVICE_FILE}" .service)"
PYTHON="${PYTHON:-python3}"
SKIP_DECOMMISSION="${SKIP_DECOMMISSION:-0}"
ASSUME_YES="${ASSUME_YES:-0}"

PROD_CONFIG="${CONFIG_DIR}/config.yaml"
DB_PATH="${DATA_DIR}/devices.db"
LOG_FILE="${LOG_DIR}/simulator.log"

# ── Helpers ───────────────────────────────────────────────────────────────────
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
NC=$'\033[0m'

info()  { printf '%s[install]%s %s\n' "${GREEN}" "${NC}" "$*"; }
warn()  { printf '%s[warn]%s    %s\n' "${YELLOW}" "${NC}" "$*"; }
error() { printf '%s[error]%s   %s\n' "${RED}" "${NC}" "$*" >&2; exit 1; }

# ── Checks ────────────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || error "Must be run as root: sudo $0 $*"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

write_service_file() {
    info "Writing systemd unit to ${SERVICE_FILE}..."
    cat >"${SERVICE_FILE}" <<SERVICE
[Unit]
Description=Mender Fleet Simulator
Documentation=https://github.com/your-org/mender-simulator
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}

WorkingDirectory=${INSTALL_DIR}

Environment=PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONUNBUFFERED=1

ExecStart=${VENV_DIR}/bin/python -m mender_simulator -c ${PROD_CONFIG}
ExecReload=/bin/kill -HUP \$MAINPID

TimeoutStopSec=30
Restart=on-failure
RestartSec=10

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=${DATA_DIR}
ReadWritePaths=${LOG_DIR}

# Logging (stdout → journal; Python also writes to log_file in config)
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
SERVICE
    chmod 644 "${SERVICE_FILE}"
}

# ── Uninstall ─────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--uninstall" ]]; then
    info "Stopping and disabling service..."
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true

    # Attempt to decommission devices from the Mender server before wiping data.
    if [[ "${SKIP_DECOMMISSION}" != "1" ]] \
        && [[ -f "${PROD_CONFIG}" ]] \
        && [[ -x "${VENV_DIR}/bin/python" ]]; then
        info "Decommissioning devices from the Mender server..."
        decommission_args=(-c "${PROD_CONFIG}")
        if [[ "${ASSUME_YES}" == "1" ]]; then
            decommission_args+=(--yes)
        fi
        if ! "${VENV_DIR}/bin/python" -m mender_simulator.decommission \
                "${decommission_args[@]}"; then
            warn "Device decommission step reported errors — continuing uninstall."
        fi
    else
        warn "Skipping remote decommission (set SKIP_DECOMMISSION=0 and ensure" \
             "config + venv are present to enable it)."
    fi

    info "Removing service file..."
    rm -f "${SERVICE_FILE}"
    systemctl daemon-reload

    info "Removing installation directory (${INSTALL_DIR})..."
    rm -rf "${INSTALL_DIR}"

    info "Removing data directory (${DATA_DIR})..."
    rm -rf "${DATA_DIR}"

    info "Removing log directory (${LOG_DIR})..."
    rm -rf "${LOG_DIR}"

    # Also remove CONFIG_DIR if it lives outside INSTALL_DIR (user configured it elsewhere).
    if [[ -d "${CONFIG_DIR}" && "${CONFIG_DIR}" != "${INSTALL_DIR}/"* ]]; then
        info "Removing config directory (${CONFIG_DIR})..."
        rm -rf "${CONFIG_DIR}"
    fi

    if id "${SERVICE_USER}" &>/dev/null; then
        info "Removing service user '${SERVICE_USER}'..."
        userdel "${SERVICE_USER}" 2>/dev/null || true
    fi

    info "Uninstall complete."
    exit 0
fi

# ── Update ────────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--update" ]]; then
    info "Updating Mender Fleet Simulator (preserving config and data)..."

    # Stop service if running
    if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
        info "Stopping service..."
        systemctl stop "${SERVICE_NAME}"
    fi

    # Python version check
    PY_VERSION="$("${PYTHON}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    PY_MAJOR="${PY_VERSION%%.*}"
    PY_MINOR="${PY_VERSION##*.}"
    if (( PY_MAJOR < 3 )) || { (( PY_MAJOR == 3 )) && (( PY_MINOR < 9 )); }; then
        error "Python 3.9+ required (found ${PY_VERSION})."
    fi

    # Reinstall package
    if [[ ! -d "${VENV_DIR}" ]]; then
        info "Creating virtual environment at ${VENV_DIR}..."
        "${PYTHON}" -m venv "${VENV_DIR}"
    fi
    info "Upgrading package..."
    "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
    "${VENV_DIR}/bin/pip" install --quiet --upgrade "${SCRIPT_DIR}"

    # Update service file and permissions
    chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_DIR}"
    write_service_file
    systemctl daemon-reload

    # Restart service
    info "Starting service..."
    systemctl start "${SERVICE_NAME}"
    sleep 2
    systemctl status "${SERVICE_NAME}" --no-pager -l || true

    NEW_VERSION="$("${VENV_DIR}/bin/python" -c 'from mender_simulator import __version__; print(__version__)' 2>/dev/null || echo "unknown")"
    echo
    info "Update complete — version ${NEW_VERSION}"
    exit 0
fi

# ── Python version check ──────────────────────────────────────────────────────
PY_VERSION="$("${PYTHON}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="${PY_VERSION%%.*}"
PY_MINOR="${PY_VERSION##*.}"
if (( PY_MAJOR < 3 )) || { (( PY_MAJOR == 3 )) && (( PY_MINOR < 9 )); }; then
    error "Python 3.9+ required (found ${PY_VERSION}). Set PYTHON=/path/to/python3.9 and retry."
fi
PY_EXEC="$("${PYTHON}" -c 'import sys; print(sys.executable)')"
info "Using Python ${PY_VERSION} (${PY_EXEC})"

# ── Service user ──────────────────────────────────────────────────────────────
if ! id "${SERVICE_USER}" &>/dev/null; then
    info "Creating system user '${SERVICE_USER}'..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
else
    info "User '${SERVICE_USER}' already exists."
fi

# ── Directories ───────────────────────────────────────────────────────────────
info "Creating directories..."
install -d -m 755 "${INSTALL_DIR}"
install -d -m 755 "${CONFIG_DIR}"
install -d -m 750 -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" "${DATA_DIR}"
install -d -m 750 -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" "${LOG_DIR}"

# ── Install package into venv ─────────────────────────────────────────────────
if [[ ! -d "${VENV_DIR}" ]]; then
    info "Creating virtual environment at ${VENV_DIR}..."
    "${PYTHON}" -m venv "${VENV_DIR}"
fi

info "Installing package..."
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet "${SCRIPT_DIR}"

# ── Config ────────────────────────────────────────────────────────────────────
if [[ -f "${PROD_CONFIG}" ]]; then
    warn "Config already exists at ${PROD_CONFIG} — not overwriting."
    warn "Edit it manually if you need to change tokens, paths or device counts."
else
    info "Installing default config to ${PROD_CONFIG}..."
    cp "${SCRIPT_DIR}/config/config.yaml" "${PROD_CONFIG}"

    # Rewrite paths to absolute production values based on configured dirs.
    sed -i.bak \
        -e "s|^\\([[:space:]]*log_file:\\).*|\\1 \"${LOG_FILE}\"|" \
        -e "s|^\\([[:space:]]*database_path:\\).*|\\1 \"${DB_PATH}\"|" \
        "${PROD_CONFIG}"
    rm -f "${PROD_CONFIG}.bak"

    if [[ -f /etc/mender/mender.conf ]]; then
        warn "──────────────────────────────────────────────────────────"
        warn "server.url and server.tenant_token are empty."
        warn "Falling back to /etc/mender/mender.conf for these values."
        warn "Set server.personal_access_token in ${PROD_CONFIG} for preauthorization."
        warn "──────────────────────────────────────────────────────────"
    else
        warn "──────────────────────────────────────────────────────────"
        warn "ACTION REQUIRED: Edit ${PROD_CONFIG}"
        warn "  - Set server.url"
        warn "  - Set server.tenant_token"
        warn "  - Set server.personal_access_token  (for preauthorization)"
        warn "/etc/mender/mender.conf not found — no fallback available."
        warn "──────────────────────────────────────────────────────────"
    fi
fi

# ── Permissions ───────────────────────────────────────────────────────────────
info "Setting permissions..."
chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_DIR}" "${DATA_DIR}" "${LOG_DIR}"
# CONFIG_DIR may live outside INSTALL_DIR; ensure service user can read it.
chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${CONFIG_DIR}"
chmod 750 "${DATA_DIR}" "${LOG_DIR}"
chmod 640 "${PROD_CONFIG}"   # config may contain tokens

# ── Systemd service ───────────────────────────────────────────────────────────
write_service_file
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

# Only start if config looks ready (tokens filled in or mender.conf fallback available)
if grep -q 'YOUR_TENANT_TOKEN_HERE\|tenant_token: ""' "${PROD_CONFIG}" 2>/dev/null \
    && [[ ! -f /etc/mender/mender.conf ]]; then
    warn "Service installed but NOT started — edit ${PROD_CONFIG} first, then run:"
    warn "  sudo systemctl start ${SERVICE_NAME}"
else
    info "Starting service..."
    systemctl restart "${SERVICE_NAME}"
    sleep 2
    systemctl status "${SERVICE_NAME}" --no-pager -l || true
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo
info "Installation complete."
echo "  Install : ${INSTALL_DIR}"
echo "  Config  : ${PROD_CONFIG}"
echo "  Data    : ${DATA_DIR}"
echo "  Logs    : journalctl -u ${SERVICE_NAME} -f"
echo "            tail -f ${LOG_FILE}"
echo "  Manage  : sudo systemctl {start|stop|restart|status} ${SERVICE_NAME}"
echo "  Remove  : sudo $0 --uninstall"
