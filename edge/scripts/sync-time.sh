#!/bin/bash
# sync-time.sh — GPS -> authenticated Headend HTTPS time fallback.
# No direct Internet/NTP fallback is used by the Edge.
set -euo pipefail

HEADEND_URL="${TIMELAPSE_HEADEND_URL:-${HEADEND_URL:-}}"
LOG="/var/log.hdd/timelapse/time-sync.log"

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') [time-sync] $*" | tee -a "$LOG" 2>/dev/null || echo "$*"; }

mkdir -p "$(dirname "$LOG")"

# GPS is the primary source. gpsd can have a valid fix even when chrony is
# using a stale/non-GPS refclock, so do not infer GPS validity from chrony.
GPS_UNIX=""
if command -v gpspipe &>/dev/null; then
    GPS_UNIX=$(timeout 8 gpspipe -w -n 20 2>/dev/null | python3 -c '
import datetime
import json
import sys

for line in sys.stdin:
    try:
        message = json.loads(line)
        if message.get("class") != "TPV" or int(message.get("mode", 0)) < 2:
            continue
        stamp = message.get("time")
        if not stamp:
            continue
        value = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        print(int(value.timestamp()))
        break
    except (ValueError, TypeError, json.JSONDecodeError):
        continue
' || true)
fi

if [[ "$GPS_UNIX" =~ ^[0-9]+$ && "$GPS_UNIX" -gt 1000000000 ]]; then
    CURRENT=$(date +%s)
    DIFF=$(( GPS_UNIX - CURRENT ))
    DIFF_ABS=${DIFF#-}
    if [[ $DIFF_ABS -gt 5 ]]; then
        log "Sætter ur fra valideret GPS-fix (forskel: ${DIFF}s)"
        date -u -s "@$GPS_UNIX" >/dev/null
    else
        log "GPS-fix er tilgængeligt og uret er korrekt (forskel: ${DIFF}s)"
    fi
    # Do not let an old non-GPS chrony sample immediately undo a valid GPS set.
    chronyc offline 2>/dev/null || true
    exit 0
fi

if command -v chronyc &>/dev/null; then
    TRACKING=$(chronyc tracking 2>/dev/null || true)
    SYSTEM_OFFSET=$(echo "$TRACKING" | awk '/^System time/ {print $4}' | tr -d '-')
    if echo "$TRACKING" | grep -q "Reference ID.*GPS\|Reference ID.*PPS" && \
       [[ "$SYSTEM_OFFSET" =~ ^[0-9]+([.][0-9]+)?$ ]] && awk "BEGIN {exit !($SYSTEM_OFFSET <= 5)}"; then
        log "Tid synkroniseret via GPS/PPS chrony-kilde (offset: ${SYSTEM_OFFSET}s)"
        chronyc offline 2>/dev/null || true
        exit 0
    fi
    chronyc online 2>/dev/null || true
    if echo "$TRACKING" | grep -q "Leap status.*Normal" && \
       [[ "$SYSTEM_OFFSET" =~ ^[0-9]+([.][0-9]+)?$ ]] && awk "BEGIN {exit !($SYSTEM_OFFSET <= 5)}"; then
        log "Tid synkroniseret via lokal chrony-kilde (offset: ${SYSTEM_OFFSET}s)"
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
