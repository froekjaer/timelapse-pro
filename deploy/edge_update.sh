#!/bin/bash
set -euo pipefail

if [ "${TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE:-0}" != "1" ]; then
    echo "Legacy git-based Edge update is disabled. Use Headend signed artifacts." >&2
    exit 2
fi

REPO_DIR="/opt/timelapse"
LOG_TAG="timelapse-edge-update"
LOCK_FILE="/tmp/timelapse_edge_update.lock"

log() { logger -t "$LOG_TAG" "$1"; echo "$(date '+%Y-%m-%d %H:%M:%S') $1"; }

if [ -f "$LOCK_FILE" ]; then
    log "Opdatering allerede i gang"; exit 0
fi
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

import_gpg_key() {
    local keyfile="$REPO_DIR/deployment/keys/timelapse-pro-public.asc"
    if [ -f "$keyfile" ]; then
        gpg --batch --import "$keyfile" 2>/dev/null || true
    fi
}

verify_latest_signed_tag() {
    local tag
    tag=$(git -C "$REPO_DIR" tag --sort=-version:refname | head -n1)
    if [ -z "$tag" ]; then
        log "ADVARSEL: Ingen tags fundet — springer GPG-check over"
        return 0
    fi
    log "Verificerer GPG-signatur paa tag: $tag"
    if git -C "$REPO_DIR" tag -v "$tag" 2>&1 | grep -qE "Good signature|God underskrift"; then
        log "GPG OK: $tag"
    else
        log "FEJL: Ugyldig GPG-signatur paa $tag — opdatering AFBRUDT"
        exit 1
    fi
}


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

import_gpg_key
verify_latest_signed_tag

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
