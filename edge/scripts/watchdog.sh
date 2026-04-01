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
RELAY_GPIO_PIN="${TIMELAPSE_RELAY_PIN:-18}"
GPIO_PATH="/sys/class/gpio"
LOG_TAG="timelapse-watchdog"
MAX_AGENT_DOWN_SECONDS=120   # restart agent if down longer than this

log() {
    logger -t "$LOG_TAG" "$*"
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

# ── GPIO relay safety ──────────────────────────────────────────────────────────
# If the agent crashes with the relay ON, the camera stays powered indefinitely.
# This watchdog cuts power if the agent has been down for > MAX_AGENT_DOWN_SECONDS.

ensure_relay_safe() {
    # Check if GPIO is exported
    if [[ ! -d "$GPIO_PATH/gpio${RELAY_GPIO_PIN}" ]]; then
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
            log "Agent down ${down_s}s — forcing relay OFF (pin ${RELAY_GPIO_PIN})"
            # Active-low relay: write 1 to open relay (camera off)
            echo 1 > "$GPIO_PATH/gpio${RELAY_GPIO_PIN}/value" 2>/dev/null || true
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
