#!/bin/bash
# Time-bounded maintenance control for timelapse-edge.service.
# A direct `systemctl stop timelapse-edge` is deliberately recovered by the
# independent watchdog. Use this helper when an intentional short stop is
# required; the hold can never exceed 15 minutes and expires fail-safe.

set -euo pipefail

SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl}"
MARKER="${WATCHDOG_MAINTENANCE_UNTIL_FILE:-/run/timelapse/edge-agent-maintenance-until}"
MAX_MINUTES=15

usage() {
    echo "Usage: $0 stop <1-${MAX_MINUTES} minutes> [reason] | start | status" >&2
    exit 2
}

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo "Must run as root (use sudo)." >&2
        exit 1
    fi
}

case "${1:-}" in
    stop)
        require_root
        minutes="${2:-}"
        [[ "$minutes" =~ ^[0-9]+$ ]] || usage
        (( minutes >= 1 && minutes <= MAX_MINUTES )) || usage
        reason="${3:-planned maintenance}"
        mkdir -p "$(dirname "$MARKER")"
        tmp="${MARKER}.tmp.$$"
        trap 'rm -f -- "${tmp:-}"' EXIT
        umask 077
        printf '%s\n%s\n' "$(( $(date +%s) + minutes * 60 ))" "$reason" > "$tmp"
        chown root:root "$tmp"
        chmod 0600 "$tmp"
        mv -f -- "$tmp" "$MARKER"
        if ! "$SYSTEMCTL_BIN" stop timelapse-edge.service; then
            rm -f -- "$MARKER"
            echo "Stop failed; maintenance hold removed and recovery remains armed." >&2
            exit 1
        fi
        echo "timelapse-edge stopped for at most ${minutes} minute(s); watchdog recovery remains armed."
        ;;
    start)
        require_root
        rm -f -- "$MARKER"
        "$SYSTEMCTL_BIN" start timelapse-edge.service
        "$SYSTEMCTL_BIN" is-active --quiet timelapse-edge.service
        echo "timelapse-edge active; maintenance hold removed."
        ;;
    status)
        "$SYSTEMCTL_BIN" status timelapse-edge.service --no-pager || true
        if [[ -f "$MARKER" && ! -L "$MARKER" ]]; then
            IFS= read -r until < "$MARKER" || until=0
            now=$(date +%s)
            if [[ "$until" =~ ^[0-9]+$ ]] && (( until > now )); then
                echo "Maintenance hold: $(( until - now )) second(s) remaining."
                exit 0
            fi
        fi
        echo "Maintenance hold: none."
        ;;
    *) usage ;;
esac
