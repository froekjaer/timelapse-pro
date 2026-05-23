#!/bin/bash
# TimeLapse Pro — Headend Deploy Poller
# Kører hvert minut via systemd timer

set -euo pipefail

if [ "${TIMELAPSE_ENABLE_LEGACY_GIT_DEPLOY:-0}" != "1" ]; then
    echo "Legacy git-based Headend deploy poller is disabled. Use signed release workflow." >&2
    exit 0
fi

REPO_DIR="/home/peter/timelapse-pro"
UI_SRC_DIR="/home/peter/timelapse-ui"
UI_DIST_DIR="/home/peter/timelapse-ui/dist"
LOG_TAG="timelapse-deploy"
DB_PATH="/home/peter/headend/timelapse_headend.db"
LOCK_FILE="/tmp/timelapse_deploy.lock"

log() { logger -t "$LOG_TAG" "$1"; echo "$(date '+%Y-%m-%d %H:%M:%S') $1"; }

if [ -f "$LOCK_FILE" ]; then
    log "Deploy allerede i gang — springer over"
    exit 0
fi
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

cd "$REPO_DIR" || { log "FEJL: Kan ikke finde $REPO_DIR"; exit 1; }

git fetch origin main --quiet 2>/dev/null || { log "FEJL: git fetch fejlede"; exit 0; }

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

log "Ny kode fundet: ${LOCAL:0:7} → ${REMOTE:0:7}"

git pull origin main --quiet

sudo systemctl restart timelapse-headend
sleep 3

if ! systemctl is-active --quiet timelapse-headend; then
    log "FEJL: timelapse-headend startede ikke — ruller tilbage"
    git revert HEAD --no-edit
    sudo systemctl restart timelapse-headend
    exit 1
fi

log "Headend deployet OK — version ${REMOTE:0:7}"

python3 << PYEOF
import sqlite3, json, sys
from datetime import datetime, timezone, timedelta
try:
    conn = sqlite3.connect("$DB_PATH")
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    devices = conn.execute(
        "SELECT device_id, device_config FROM devices WHERE last_seen > ?",
        (cutoff,)
    ).fetchall()
    count = 0
    for d in devices:
        cfg = json.loads(d["device_config"] or "{}")
        cfg["update_requested"] = True
        cfg["update_version"] = "${REMOTE:0:7}"
        conn.execute(
            "UPDATE devices SET device_config = ? WHERE device_id = ?",
            (json.dumps(cfg), d["device_id"])
        )
        count += 1
    conn.commit()
    conn.close()
    print(f"update_requested sat for {count} edge enheder")
except Exception as e:
    print(f"DB fejl: {e}", file=sys.stderr)
PYEOF

log "Deploy fuldført — version ${REMOTE:0:7}"
