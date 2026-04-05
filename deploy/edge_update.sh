#!/bin/bash
# TimeLapse Pro — Edge Self-Update Script
# Køres af agent når update_requested flag er sat

set -euo pipefail

REPO_DIR="/opt/timelapse"
LOG_TAG="timelapse-edge-update"
LOCK_FILE="/tmp/timelapse_edge_update.lock"

log() { logger -t "$LOG_TAG" "$1"; echo "$(date '+%Y-%m-%d %H:%M:%S') $1"; }

if [ -f "$LOCK_FILE" ]; then
    log "Opdatering allerede i gang"
    exit 0
fi
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

cd "$REPO_DIR"

CURRENT=$(git rev-parse HEAD)

git fetch origin main --quiet 2>/dev/null || {
    log "FEJL: git fetch fejlede"
    exit 1
}

REMOTE=$(git rev-parse origin/main)

if [ "$CURRENT" = "$REMOTE" ]; then
    log "Allerede opdateret — ingen ændringer"
    exit 0
fi

log "Opdaterer: ${CURRENT:0:7} → ${REMOTE:0:7}"

git pull origin main --quiet

find /opt/timelapse/edge -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

log "Opdatering OK — genstarter timelapse-edge"

sudo systemctl restart timelapse-edge
