#!/bin/bash
# sync-time.sh — GPS -> authenticated Headend HTTPS time fallback.
# No direct Internet/NTP fallback is used by the Edge.
set -euo pipefail

HEADEND_URL="${TIMELAPSE_HEADEND_URL:-${HEADEND_URL:-}}"
LOG="/var/log.hdd/timelapse/time-sync.log"

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') [time-sync] $*" | tee -a "$LOG" 2>/dev/null || echo "$*"; }

mkdir -p "$(dirname "$LOG")"

if command -v chronyc &>/dev/null; then
    TRACKING=$(chronyc tracking 2>/dev/null || true)
    if echo "$TRACKING" | grep -q "Reference ID.*GPS\|Reference ID.*PPS"; then
        OFFSET=$(echo "$TRACKING" | grep "System time" | awk '{print $4}' | tr -d '-')
        log "GPS synkroniseret (offset: ${OFFSET}s)"
        exit 0
    fi
    if echo "$TRACKING" | grep -qE "Leap status.*Normal|stratum [1-4]"; then
        log "Tid synkroniseret via lokal chrony-kilde"
        exit 0
    fi
fi

if [[ ! "$HEADEND_URL" =~ ^https:// ]]; then
    log "Ingen HTTPS Headend-tidskilde konfigureret; beholder lokalt ur"
    exit 1
fi

HEADEND_URL="${HEADEND_URL%/}"
TIME_URL="${HEADEND_URL}/api/time"
if [[ "$HEADEND_URL" == */api ]]; then
    TIME_URL="${HEADEND_URL}/time"
fi
log "GPS ikke tilgængeligt — prøver Headend-tid via HTTPS"
RESPONSE=$(curl --fail --silent --show-error --max-time 5 "$TIME_URL" 2>/dev/null || true)

if [[ -n "$RESPONSE" ]]; then
    UNIX_TIME=$(echo "$RESPONSE" | python3 -c "import sys,json; print(int(json.load(sys.stdin)['unix']))" 2>/dev/null || true)
    if [[ -n "$UNIX_TIME" && "$UNIX_TIME" -gt 1000000000 ]]; then
        CURRENT=$(date +%s)
        DIFF=$(( UNIX_TIME - CURRENT ))
        DIFF_ABS=${DIFF#-}
        if [[ $DIFF_ABS -gt 5 ]]; then
            log "Sætter ur fra Headend (forskel: ${DIFF}s)"
            date -s "@$UNIX_TIME" >/dev/null
            chronyc makestep 2>/dev/null || true
        else
            log "Ur er allerede korrekt (forskel: ${DIFF}s)"
        fi
        exit 0
    fi
fi

log "ADVARSEL: GPS og Headend-tidskilde er ikke tilgængelige"
exit 1
