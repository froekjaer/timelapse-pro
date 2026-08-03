#!/bin/bash
# Encrypted, deduplicated backup of the Mac project workspace.
#
# The active workspace is never synchronized by a cloud client. Restic writes
# snapshots to the logical TimeLapse data root; only the closed repository is
# mirrored to OneDrive after integrity validation.
set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

DATA_ROOT="${TIMELAPSE_DATA_ROOT:-/data-fast}"
PROJECTS_ROOT="${PROJECTS_ROOT:-${DATA_ROOT}/peter-home/projects}"
BACKUP_ROOT="${PROJECT_BACKUP_ROOT:-${DATA_ROOT}/backup/project-snapshots}"
RESTIC_REPOSITORY="${PROJECT_BACKUP_REPOSITORY:-${BACKUP_ROOT}/restic-repository}"
ONEDRIVE_ROOT="${PROJECT_BACKUP_ONEDRIVE_ROOT:-${HOME}/Library/CloudStorage/OneDrive-Personligt/Filer/Projektbackups}"
ONEDRIVE_REPOSITORY="${ONEDRIVE_ROOT}/restic-repository"
ONEDRIVE_MARKER="${ONEDRIVE_ROOT}/.timelapse-project-backup-repository"
STATE_DIR="${BACKUP_ROOT}/state"
LOCK_DIR="${BACKUP_ROOT}/.backup.lock"
LOG_FILE="${BACKUP_ROOT}/project-snapshot.log"
KEYCHAIN_SERVICE="${PROJECT_BACKUP_KEYCHAIN_SERVICE:-dk.froekjaer.timelapse.project-backup.restic}"

KEEP_DAILY="${PROJECT_BACKUP_KEEP_DAILY:-30}"
KEEP_MONTHLY="${PROJECT_BACKUP_KEEP_MONTHLY:-12}"
KEEP_YEARLY="${PROJECT_BACKUP_KEEP_YEARLY:-3}"

DRY_RUN=false
FORCE_CHECK=false

log() {
  local message="$1"
  printf '%s [project-snapshot] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$message" | tee -a "$LOG_FILE"
}

die() {
  log "ERROR: $1"
  exit 1
}

usage() {
  cat <<'EOF'
Usage: project_snapshot_backup.sh [--dry-run] [--check]

Creates an encrypted, deduplicated backup of project source and project
artifacts. The live project tree is never copied directly to a cloud client.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --check) FORCE_CHECK=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

[[ -d "$DATA_ROOT" ]] || die "logical data root is unavailable: $DATA_ROOT"
[[ -d "$PROJECTS_ROOT" ]] || die "project root is unavailable: $PROJECTS_ROOT"
command -v restic >/dev/null || die "restic is not installed"
command -v rsync >/dev/null || die "rsync is not installed"
command -v security >/dev/null || die "macOS Keychain CLI is not available"

mkdir -p "$BACKUP_ROOT" "$STATE_DIR"
touch "$LOG_FILE"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  die "another project snapshot process is already running"
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

if ! security find-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" -w >/dev/null 2>&1; then
  if [[ "$DRY_RUN" == true ]]; then
    log "would create the Keychain entry for the backup repository"
  else
    password="$(openssl rand -base64 48)"
    security add-generic-password -U -a "$USER" -s "$KEYCHAIN_SERVICE" -w "$password" >/dev/null
    unset password
    log "created encrypted repository credential in the macOS Keychain"
  fi
fi

export RESTIC_REPOSITORY
export RESTIC_PASSWORD_COMMAND="/usr/bin/security find-generic-password -a '${USER}' -s '${KEYCHAIN_SERVICE}' -w"

EXCLUDES=(
  --exclude "${PROJECTS_ROOT}/Downloads"
  --exclude "${PROJECTS_ROOT}/openwebui-env"
  --exclude "${PROJECTS_ROOT}/timelapse-pro-backup"
  --exclude "${PROJECTS_ROOT}/timelapse-pro/.base_image_cache"
  --exclude "${PROJECTS_ROOT}/timelapse-pro/artifacts"
  --exclude "**/.DS_Store"
  --exclude "**/node_modules"
  --exclude "**/.venv"
  --exclude "**/venv"
  --exclude "**/__pycache__"
  --exclude "**/.pytest_cache"
  --exclude "**/.mypy_cache"
  --exclude "**/.ruff_cache"
  --exclude "**/.cache"
  --exclude "**/dist"
  --exclude "**/build"
)

write_inventory() {
  local inventory="${STATE_DIR}/project-inventory.txt"
  {
    printf 'created_at=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'data_root=%s\n' "$DATA_ROOT"
    printf 'projects_root=%s\n' "$PROJECTS_ROOT"
    printf 'excluded=%s\n' "Downloads, openwebui-env, timelapse-pro-backup, base-image-cache, generated artifacts, dependency/build caches"
    printf '\n[git repositories]\n'
    while IFS= read -r git_dir; do
      repo="${git_dir%/.git}"
      printf '%s\t%s\t%s\n' "$repo" \
        "$(git -C "$repo" rev-parse HEAD 2>/dev/null || printf 'no-head')" \
        "$(git -C "$repo" status --porcelain=v1 2>/dev/null | wc -l | tr -d ' ')"
    done < <(find "$PROJECTS_ROOT" -type d -name .git -prune -print 2>/dev/null | sort)
  } > "$inventory"
}

if [[ "$DRY_RUN" == true ]]; then
  log "DRY RUN: source=$PROJECTS_ROOT local_repo=$RESTIC_REPOSITORY cloud_repo=$ONEDRIVE_REPOSITORY"
  printf '%s\n' "${EXCLUDES[@]}"
  exit 0
fi

write_inventory

if [[ ! -f "${RESTIC_REPOSITORY}/config" ]]; then
  log "initializing encrypted local restic repository"
  restic init
fi

SOURCES=("$PROJECTS_ROOT" "$STATE_DIR")
if [[ -d "${DATA_ROOT}/backup/timelapse-artifacts" ]]; then
  SOURCES+=("${DATA_ROOT}/backup/timelapse-artifacts")
fi

log "creating deduplicated project snapshot"
restic backup --one-file-system --tag mac-mini --tag project-workspace --tag "$(date '+%Y-%m-%d')" "${EXCLUDES[@]}" "${SOURCES[@]}"

log "applying retention: daily=${KEEP_DAILY}, monthly=${KEEP_MONTHLY}, yearly=${KEEP_YEARLY}"
restic forget --tag project-workspace --keep-daily "$KEEP_DAILY" --keep-monthly "$KEEP_MONTHLY" --keep-yearly "$KEEP_YEARLY" --prune

if [[ "$FORCE_CHECK" == true || "$(date '+%u')" == "7" ]]; then
  log "running repository integrity check"
  restic check --read-data-subset=1/100
fi

restic snapshots --tag project-workspace --json > "${STATE_DIR}/latest-snapshots.json"
shasum -a 256 "${STATE_DIR}/latest-snapshots.json" > "${STATE_DIR}/latest-snapshots.json.sha256"

if [[ -e "$ONEDRIVE_ROOT" && ! -f "$ONEDRIVE_MARKER" ]] && [[ -n "$(find "$ONEDRIVE_ROOT" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  die "OneDrive destination is not an empty TimeLapse backup folder: $ONEDRIVE_ROOT"
fi

mkdir -p "$ONEDRIVE_REPOSITORY"
printf 'Managed by TimeLapse project snapshot backup. Do not remove.\n' > "$ONEDRIVE_MARKER"
log "mirroring completed repository to OneDrive staging folder"
rsync -a --delete --exclude 'locks/' "${RESTIC_REPOSITORY}/" "${ONEDRIVE_REPOSITORY}/"
cp "${STATE_DIR}/latest-snapshots.json" "${ONEDRIVE_ROOT}/latest-snapshots.json"
cp "${STATE_DIR}/latest-snapshots.json.sha256" "${ONEDRIVE_ROOT}/latest-snapshots.json.sha256"

cat > "${ONEDRIVE_ROOT}/README-RESTORE.txt" <<'EOF'
TimeLapse project backup repository

This is an encrypted restic repository mirrored from the local data disk.
Do not edit or delete files in restic-repository manually.

Restore requires the TimeLapse project backup credential from the macOS Keychain
and the restic tool. The source project root and exclusion policy are recorded
in the latest snapshot inventory.
EOF

log "snapshot completed successfully"
