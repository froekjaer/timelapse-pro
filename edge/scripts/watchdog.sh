#!/bin/bash
# TimeLapse Pro — Edge Watchdog
# ===============================
# Secondary watchdog that checks the main agent is alive and the
# GPIO relay is in a safe state. Intentionally minimal — no Python,
# no dependencies that could fail in the same way as the main agent.
#
# Installed as: /opt/timelapse/edge/scripts/watchdog.sh
# Runs as: timelapse-watchdog.service (root, Restart=always)

set -euo pipefail

AGENT_SERVICE="timelapse-edge"
CONFIG_PATH="${TIMELAPSE_CONFIG_PATH:-/opt/timelapse/edge/config.yaml}"
GPIO_PATH="/sys/class/gpio"
LOG_TAG="timelapse-watchdog"
MAX_AGENT_DOWN_SECONDS=120   # restart agent if down longer than this
RELAY_OFF_VALUE="1"          # HW-383A active-low: 1 = relay OFF
RELAY_ON_VALUE="0"           # HW-383A active-low: 0 = relay ON

log() {
    logger -t "$LOG_TAG" "$*"
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

read_config_value() {
    local section="$1"
    local key="$2"
    awk -v section="$section" -v key="$key" '
        /^[^[:space:]#][^:]*:/ { in_section = 0 }
        $0 ~ "^[[:space:]]*" section ":[[:space:]]*$" { in_section = 1; next }
        in_section && $0 ~ "^[[:space:]]*" key ":[[:space:]]*" {
            value = $0
            sub("^[[:space:]]*" key ":[[:space:]]*", "", value)
            sub(/[[:space:]]+#.*/, "", value)
            gsub(/["'\''[:space:]]/, "", value)
            print value
            exit
        }
    ' "$CONFIG_PATH"
}

resolve_camera_relay_gpio_pin() {
    if [[ -n "${TIMELAPSE_CAMERA_RELAY_PIN:-${TIMELAPSE_RELAY_PIN:-}}" ]]; then
        local override="${TIMELAPSE_CAMERA_RELAY_PIN:-${TIMELAPSE_RELAY_PIN:-}}"
        if [[ "$override" =~ ^[0-9]+$ ]]; then
            echo "$override"
            return 0
        fi
        log "ERROR: camera relay pin override is not numeric; refusing relay safety action"
        return 1
    fi

    if [[ ! -r "$CONFIG_PATH" ]]; then
        log "ERROR: Edge config not readable at $CONFIG_PATH; refusing relay safety action"
        return 1
    fi

    local pin
    pin=$(read_config_value "camera" "relay_gpio_pin")

    if [[ "$pin" =~ ^[0-9]+$ ]]; then
        echo "$pin"
        return 0
    fi

    log "ERROR: camera.relay_gpio_pin missing or invalid in $CONFIG_PATH; refusing relay safety action"
    return 1
}

resolve_modem_relay_gpio_pin() {
    if [[ -n "${TIMELAPSE_MODEM_RELAY_PIN:-}" ]]; then
        if [[ "${TIMELAPSE_MODEM_RELAY_PIN}" =~ ^[0-9]+$ ]]; then
            echo "${TIMELAPSE_MODEM_RELAY_PIN}"
            return 0
        fi
        log "ERROR: modem relay pin override is not numeric; leaving modem relay unchanged"
        return 1
    fi

    if [[ ! -r "$CONFIG_PATH" ]]; then
        log "ERROR: Edge config not readable at $CONFIG_PATH; leaving modem relay unchanged"
        return 1
    fi

    local pin
    pin=$(read_config_value "modem" "modem_relay_gpio_pin")
    if [[ "$pin" =~ ^[0-9]+$ ]]; then
        echo "$pin"
        return 0
    fi
    return 1
}

# ── GPIO relay safety ──────────────────────────────────────────────────────────
# If the agent crashes with the relay ON, the camera stays powered indefinitely.
# This watchdog applies device config: camera relay OFF, modem relay ON for recovery.

ensure_relay_safe() {
    local camera_relay_gpio_pin
    camera_relay_gpio_pin=$(resolve_camera_relay_gpio_pin) || return 1

    # Check if GPIO is exported
    if [[ ! -d "$GPIO_PATH/gpio${camera_relay_gpio_pin}" ]]; then
        return 0   # GPIO not active — relay is definitely off
    fi

    local agent_active
    agent_active=$(systemctl is-active "$AGENT_SERVICE" 2>/dev/null || echo "inactive")

    if [[ "$agent_active" != "active" ]]; then
        local inactive_since
        inactive_since=$(systemctl show "$AGENT_SERVICE" \
            --property=InactiveEnterTimestampMonotonic \
            --value 2>/dev/null || echo "0")
        local now_mono
        now_mono=$(cut -d. -f1 /proc/uptime)

        # Convert microseconds to seconds
        local down_s=$(( (${now_mono%.*} * 1000000 - ${inactive_since:-0}) / 1000000 ))

        if (( down_s > MAX_AGENT_DOWN_SECONDS )); then
            log "Agent down ${down_s}s — applying device relay safety state"
            # Active-low relay: write 1 to open camera relay (camera off)
            echo "$RELAY_OFF_VALUE" > "$GPIO_PATH/gpio${camera_relay_gpio_pin}/value" 2>/dev/null || true
            local modem_relay_gpio_pin
            if modem_relay_gpio_pin=$(resolve_modem_relay_gpio_pin); then
                if [[ -d "$GPIO_PATH/gpio${modem_relay_gpio_pin}" ]]; then
                    # Active-low relay: write 0 to close modem relay (modem on)
                    echo "$RELAY_ON_VALUE" > "$GPIO_PATH/gpio${modem_relay_gpio_pin}/value" 2>/dev/null || true
                fi
            fi
        fi
    fi
}

# ── Agent health check ─────────────────────────────────────────────────────────

check_agent() {
    local status
    status=$(systemctl is-active "$AGENT_SERVICE" 2>/dev/null || echo "inactive")

    if [[ "$status" == "active" ]]; then
        return 0
    fi

    log "Agent not active (status: $status) — systemd will handle restart"
    ensure_relay_safe
    return 1
}

# ── Disk space emergency check ─────────────────────────────────────────────────
# Belt-and-suspenders: if /data is > 95% full, log a critical alert.
# The agent's circular buffer should prevent this, but just in case.

check_disk() {
    local used_pct
    used_pct=$(df /data 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}')
    if [[ -n "$used_pct" ]] && (( used_pct > 95 )); then
        log "CRITICAL: /data disk usage at ${used_pct}% — capture may stop"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────────

log "Watchdog tick"
check_agent || true
check_disk  || true

# Sleep interval is controlled by systemd (RestartSec in service file)
# This script exits after each check — systemd restarts it
sleep 60
