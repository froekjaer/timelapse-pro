#!/bin/bash
# sync-time.sh — GPS -> optional NTP -> authenticated Headend HTTPS time
# fallback. No direct Internet/NTP is used unless TIMELAPSE_NTP_SERVER is
# explicitly configured (e.g. a LAN NTP server) — off by default.
set -euo pipefail

HEADEND_URL="${TIMELAPSE_HEADEND_URL:-${HEADEND_URL:-}}"
NTP_SERVER="${TIMELAPSE_NTP_SERVER:-${NTP_SERVER:-}}"
LOG="/var/log.hdd/timelapse/time-sync.log"

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') [time-sync] $*" | tee -a "$LOG" 2>/dev/null || echo "$*"; }

mkdir -p "$(dirname "$LOG")"

# GPS is the primary source. gpsd can have a valid fix even when chrony is
# using a stale/non-GPS refclock, so do not infer GPS validity from chrony.
#
# The camera and GPS module share a power rail, so GPS loses power (and
# needs to reacquire) on every capture (Peter, 2026-09-09). Right after
# power returns, gpsd's very first reading(s) before the fix has genuinely
# settled can be a transient bad value, so a single TPV read is not enough
# to trust — only accept a time once two consecutive readings are mutually
# consistent (GPS-reported time advances in lockstep with real, monotonic
# elapsed time between the two reads). Deliberately does not rely on
# disabling chrony's SHM refclock "trust" flag: these devices have no RTC,
# so GPS is the only time source to fall back on, and "trust" is what lets
# chrony keep using it as sole source at all.
GPS_UNIX=""
if command -v gpspipe &>/dev/null; then
    GPS_UNIX=$(timeout 8 gpspipe -w -n 20 2>/dev/null | python3 -c '
import datetime
import json
import sys
import time

STABILITY_TOLERANCE_S = 2
readings = []  # (monotonic read time, gps epoch)

for line in sys.stdin:
    try:
        message = json.loads(line)
        if message.get("class") != "TPV" or int(message.get("mode", 0)) < 2:
            continue
        stamp = message.get("time")
        if not stamp:
            continue
        value = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        candidate = int(value.timestamp())
        if candidate <= 1_000_000_000:
            continue
        readings.append((time.monotonic(), candidate))
        if len(readings) >= 2:
            (t_prev, g_prev), (t_now, g_now) = readings[-2], readings[-1]
            if abs((g_now - g_prev) - (t_now - t_prev)) <= STABILITY_TOLERANCE_S:
                print(g_now)
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

# Optional NTP fallback — off by default, only used if an operator has
# explicitly configured TIMELAPSE_NTP_SERVER (e.g. a reachable LAN NTP
# server). `chronyd -q` is chrony's own documented one-shot query-and-step
# mode (the modern replacement for the deprecated `ntpdate`), so this needs
# no extra package beyond chrony, already required for GPS.
if [[ -n "$NTP_SERVER" ]] && command -v chronyd &>/dev/null; then
    log "GPS ikke tilgængeligt — prøver konfigureret NTP-server ${NTP_SERVER}"
    if chronyd -q "server ${NTP_SERVER} iburst" >>"$LOG" 2>&1; then
        log "Tid synkroniseret via konfigureret NTP-server ${NTP_SERVER}"
        exit 0
    fi
    log "NTP-server ${NTP_SERVER} svarede ikke"
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
