#!/bin/bash
set -euo pipefail

REPO_DIR="/opt/timelapse"
LOG_TAG="timelapse-edge-update"
LOCK_FILE="/tmp/timelapse_edge_update.lock"

log() { logger -t "$LOG_TAG" "$1"; echo "$(date '+%Y-%m-%d %H:%M:%S') $1"; }

if [ -f "$LOCK_FILE" ]; then
    log "Opdatering allerede i gang"; exit 0
fi
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

cd "$REPO_DIR"

CURRENT=$(git rev-parse HEAD)

# Omgå safe.directory med -C og GIT_DIR
GIT_DIR="$REPO_DIR/.git" GIT_WORK_TREE="$REPO_DIR" git fetch origin main --quiet 2>/dev/null || {
    log "FEJL: git fetch fejlede"; exit 1
}

REMOTE=$(GIT_DIR="$REPO_DIR/.git" GIT_WORK_TREE="$REPO_DIR" git rev-parse origin/main)

if [ "$CURRENT" = "$REMOTE" ]; then
    log "Allerede opdateret — ingen ændringer"; exit 0
fi

log "Opdaterer: ${CURRENT:0:7} → ${REMOTE:0:7}"

GIT_DIR="$REPO_DIR/.git" GIT_WORK_TREE="$REPO_DIR" git pull origin main --quiet
find /opt/timelapse/edge -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
log "Opdatering OK — genstarter timelapse-edge"
sudo systemctl restart timelapse-edge

# Health-check — rollback ved fejl
sleep 30
if ! systemctl is-active --quiet timelapse-edge; then
    log "FEJL: timelapse-edge startede ikke — ruller tilbage til $CURRENT"
    GIT_DIR="$REPO_DIR/.git" GIT_WORK_TREE="$REPO_DIR" git checkout "$CURRENT" --quiet
    find /opt/timelapse/edge -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    sudo systemctl restart timelapse-edge
    sleep 10
    if systemctl is-active --quiet timelapse-edge; then
        log "Rollback OK — kører igen på $CURRENT"
    else
        log "KRITISK: Rollback fejlede — manuel indgriben krævet"
    fi
    exit 1
fi
log "Health-check OK — opdatering vellykket til ${REMOTE:0:7}"
