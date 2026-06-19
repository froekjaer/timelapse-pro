#!/bin/bash
# sync-time.sh — Tidssynkronisering: GPS → headend API → NTP
# Køres ved boot (før totp-service) og periodisk via systemd timer
#
# Returnerer 0 hvis tid er synkroniseret, 1 hvis ikke
set -euo pipefail

HEADEND_URL="${HEADEND_URL:-http://192.168.86.125:8000}"
LOG="/var/log.hdd/timelapse/time-sync.log"
MAX_OFFSET_SEC=2  # Acceptabelt offset fra GPS

log() { echo "$(date -u '+%Y-%m-%d %H:%M:%S') [time-sync] $*" | tee -a "$LOG" 2>/dev/null || echo "$*"; }

mkdir -p "$(dirname "$LOG")"

# ── 1. GPS via chrony ─────────────────────────────────────────────────────────
if command -v chronyc &>/dev/null; then
    TRACKING=$(chronyc tracking 2>/dev/null || true)
    if echo "$TRACKING" | grep -q "Reference ID.*GPS\|Reference ID.*PPS"; then
        OFFSET=$(echo "$TRACKING" | grep "System time" | awk '{print $4}' | tr -d '-')
        log "GPS synkroniseret (offset: ${OFFSET}s)"
        exit 0
    fi

    # Chrony kører men bruger ikke GPS — tjek om NTP allerede synker
    if echo "$TRACKING" | grep -qE "Leap status.*Normal|stratum [1-4]"; then
        log "NTP synkroniseret via chrony"
        exit 0
    fi
fi

# ── 2. Headend API fallback ───────────────────────────────────────────────────
log "GPS ikke tilgængeligt — prøver headend API: $HEADEND_URL/api/time"

RESPONSE=$(curl -sf --max-time 5 "$HEADEND_URL/api/time" 2>/dev/null || true)

if [[ -n "$RESPONSE" ]]; then
    UNIX_TIME=$(echo "$RESPONSE" | python3 -c "import sys,json; print(int(json.load(sys.stdin)['unix']))" 2>/dev/null || true)

    if [[ -n "$UNIX_TIME" && "$UNIX_TIME" -gt 1000000000 ]]; then
        CURRENT=$(date +%s)
        DIFF=$(( UNIX_TIME - CURRENT ))
        DIFF_ABS=${DIFF#-}

        if [[ $DIFF_ABS -gt 5 ]]; then
            log "Sætter ur fra headend (forskel: ${DIFF}s)"
            date -s "@$UNIX_TIME" >/dev/null
            # Fortæl chrony om spring
            chronyc makestep 2>/dev/null || true
            log "Ur sat til: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
        else
            log "Ur er allerede korrekt (forskel: ${DIFF}s)"
        fi
        exit 0
    fi
fi

# ── 3. Ingen kilder tilgængelige ─────────────────────────────────────────────
log "ADVARSEL: Ingen tidskilder tilgængelige — ur usynkroniseret"
exit 1
