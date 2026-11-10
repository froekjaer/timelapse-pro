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
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl}"
WATCHDOG_STATE_DIR="${WATCHDOG_STATE_DIR:-/run/timelapse/watchdog}"
DOWN_SINCE_FILE="${WATCHDOG_STATE_DIR}/agent-down-since"
MAINTENANCE_UNTIL_FILE="${WATCHDOG_MAINTENANCE_UNTIL_FILE:-/run/timelapse/edge-agent-maintenance-until}"
MAX_AGENT_DOWN_SECONDS="${MAX_AGENT_DOWN_SECONDS:-60}"
MAX_MAINTENANCE_SECONDS="${MAX_MAINTENANCE_SECONDS:-900}"
CHECK_INTERVAL_SECONDS="${CHECK_INTERVAL_SECONDS:-15}"

log() {
    if command -v logger >/dev/null 2>&1; then
        logger -t "$LOG_TAG" "$*"
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

now_epoch() {
    if [[ -n "${WATCHDOG_NOW_EPOCH:-}" ]]; then
        printf '%s\n' "$WATCHDOG_NOW_EPOCH"
    else
        date +%s
    fi
}

maintenance_hold_active() {
    [[ -f "$MAINTENANCE_UNTIL_FILE" && ! -L "$MAINTENANCE_UNTIL_FILE" ]] || return 1

    local until now remaining
    IFS= read -r until < "$MAINTENANCE_UNTIL_FILE" || until=""
    now=$(now_epoch)
    if [[ ! "$until" =~ ^[0-9]+$ ]]; then
        log "Ignoring malformed maintenance hold; recovery remains armed"
        rm -f -- "$MAINTENANCE_UNTIL_FILE"
        return 1
    fi
    remaining=$(( until - now ))
    if (( remaining <= 0 )); then
        log "Maintenance hold expired; recovery re-armed"
        rm -f -- "$MAINTENANCE_UNTIL_FILE"
        return 1
    fi
    if (( remaining > MAX_MAINTENANCE_SECONDS )); then
        log "Ignoring maintenance hold beyond ${MAX_MAINTENANCE_SECONDS}s safety limit"
        rm -f -- "$MAINTENANCE_UNTIL_FILE"
        return 1
    fi
    log "Agent maintenance hold active for at most ${remaining}s"
    return 0
}

agent_down_seconds() {
    local now since
    mkdir -p "$WATCHDOG_STATE_DIR"
    now=$(now_epoch)
    if [[ ! -f "$DOWN_SINCE_FILE" ]]; then
        printf '%s\n' "$now" > "$DOWN_SINCE_FILE"
    fi
    IFS= read -r since < "$DOWN_SINCE_FILE" || since="$now"
    if [[ ! "$since" =~ ^[0-9]+$ ]] || (( since > now )); then
        since="$now"
        printf '%s\n' "$since" > "$DOWN_SINCE_FILE"
    fi
    printf '%s\n' "$(( now - since ))"
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
    agent_active=$("$SYSTEMCTL_BIN" is-active "$AGENT_SERVICE" 2>/dev/null || true)
    agent_active="${agent_active:-inactive}"

    if [[ "$agent_active" != "active" ]]; then
        local inactive_since
        inactive_since=$("$SYSTEMCTL_BIN" show "$AGENT_SERVICE" \
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
    local status down_s
    status=$("$SYSTEMCTL_BIN" is-active "$AGENT_SERVICE" 2>/dev/null || true)
    status="${status:-inactive}"

    if [[ "$status" == "active" ]]; then
        rm -f -- "$DOWN_SINCE_FILE"
        return 0
    fi

    down_s=$(agent_down_seconds)
    log "Agent not active (status: $status, observed ${down_s}s)"
    ensure_relay_safe
    if maintenance_hold_active; then
        return 1
    fi
    if (( down_s < MAX_AGENT_DOWN_SECONDS )); then
        return 1
    fi

    log "Recovery threshold reached — starting ${AGENT_SERVICE}.service"
    if ! "$SYSTEMCTL_BIN" start "${AGENT_SERVICE}.service"; then
        log "CRITICAL: failed to start ${AGENT_SERVICE}.service; retrying next watchdog tick"
        return 1
    fi
    if [[ "$("$SYSTEMCTL_BIN" is-active "$AGENT_SERVICE" 2>/dev/null || true)" != "active" ]]; then
        log "CRITICAL: ${AGENT_SERVICE}.service did not become active; retrying next watchdog tick"
        return 1
    fi
    rm -f -- "$DOWN_SINCE_FILE"
    log "Recovery successful — ${AGENT_SERVICE}.service is active"
    return 0
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

while true; do
    check_agent || true
    check_disk  || true
    if [[ "${WATCHDOG_ONCE:-0}" == "1" ]]; then
        break
    fi
    sleep "$CHECK_INTERVAL_SECONDS"
done
