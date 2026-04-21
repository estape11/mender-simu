#!/usr/bin/env bash
# apply-device-config.sh — Mender Configure apply script for the simulator.
#
# Installed to: /usr/lib/mender-configure/apply-device-config.d/mender-simulator
#
# Called by the mender-configure update module with a single argument:
#   $1 = path to /var/lib/mender-configure/device-config.json
#
# The JSON contains string key-value pairs set from the Mender UI.
# This script reads the industry count keys, updates config.yaml,
# and restarts the mender-simulator service.
#
# Expected keys in device-config.json (all values are strings):
#   {
#     "automotive": "10",
#     "smart_buildings": "5",
#     "medical": "3",
#     "industrial_iot": "8",
#     "retail": "0",
#     "ev_charging": "4"
#   }
#
# Only keys matching known industries are processed; others are ignored.
# A value of "0" effectively stops all simulators for that industry.
#
# See: https://docs.mender.io/add-ons/configure/device-integration

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
ENV_FILE="/etc/default/mender-simulator-configure"
# shellcheck source=/dev/null
[[ -f "$ENV_FILE" ]] && . "$ENV_FILE"

INSTALL_DIR="${MENDER_SIMULATOR_INSTALL_DIR:-/opt/mender-simulator}"
CONFIG_FILE="${MENDER_SIMULATOR_CONFIG:-${INSTALL_DIR}/config/config.yaml}"
SERVICE_NAME="${MENDER_SIMULATOR_SERVICE:-mender-simulator}"
VENV_PYTHON="${INSTALL_DIR}/venv/bin/python3"

# ── Helpers ───────────────────────────────────────────────────────────────────
log() { echo "mender-simulator: $*" >&2; }

# ── Argument check (mender-configure convention) ─────────────────────────────
if [[ $# -ne 1 ]]; then
    log "Usage: $0 <device-config-json>"
    exit 2
fi

CONFIG_JSON="$1"

if [[ ! -f "$CONFIG_JSON" ]]; then
    log "Config file not found: $CONFIG_JSON"
    exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
    # Simulator not installed, nothing to do — exit 0 (no-op)
    exit 0
fi

# Use the simulator's venv python (has PyYAML), fall back to system python3
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    log "python3 is required but not found"
    exit 1
fi

log "Applying configuration from $CONFIG_JSON"

# Read the JSON and update the YAML config
"$PYTHON" - "$CONFIG_JSON" "$CONFIG_FILE" >&2 <<'PYTHON'
import json
import sys
import yaml

config_json_path = sys.argv[1]
config_yaml_path = sys.argv[2]

# Read the incoming mender-configure JSON (values are strings)
with open(config_json_path, "r") as f:
    new_config = json.load(f)

if not isinstance(new_config, dict):
    print(f"ERROR: expected JSON object, got {type(new_config).__name__}", file=sys.stderr)
    sys.exit(1)

# Read the current simulator config
with open(config_yaml_path, "r") as f:
    config = yaml.safe_load(f)

industries = config.get("industries", {})
changes = []

for key, value in new_config.items():
    # Only process keys that match a known industry
    if key not in industries:
        continue

    # mender-configure sends all values as strings
    try:
        count = int(value)
    except (ValueError, TypeError):
        print(f"WARNING: ignoring non-numeric value for '{key}': {value!r}", file=sys.stderr)
        continue

    if count < 0:
        print(f"WARNING: ignoring negative count for '{key}': {count}", file=sys.stderr)
        continue

    old_count = industries[key].get("count", 0)
    if old_count != count:
        industries[key]["count"] = count
        changes.append(f"  {key}: {old_count} -> {count}")

if not changes:
    print("No changes to simulator config.")
    sys.exit(0)

# Write updated simulator config
with open(config_yaml_path, "w") as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

# Write all current counts back to device-config.json (as strings)
# so mender-configure reports the full state, not just what was changed
all_counts = {name: str(data.get("count", 0)) for name, data in industries.items()}
with open(config_json_path, "w") as f:
    json.dump(all_counts, f, indent=2)
    f.write("\n")

print("Updated industry counts:")
for change in changes:
    print(change)
PYTHON

PYTHON_EXIT=$?
if [[ $PYTHON_EXIT -ne 0 ]]; then
    log "Failed to update config"
    exit 1
fi

# Restart the simulator service so it picks up the new counts
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    log "Restarting $SERVICE_NAME..."
    systemctl restart "$SERVICE_NAME"
    log "Service restarted"
fi

exit 0
