#!/bin/bash
# Safe restore helper for the encrypted TimeLapse project snapshots.
set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

DATA_ROOT="${TIMELAPSE_DATA_ROOT:-/data-fast}"
BACKUP_ROOT="${PROJECT_BACKUP_ROOT:-${DATA_ROOT}/backup/project-snapshots}"
RESTIC_REPOSITORY="${PROJECT_BACKUP_REPOSITORY:-${BACKUP_ROOT}/restic-repository}"
ONEDRIVE_REPOSITORY="${PROJECT_BACKUP_ONEDRIVE_REPOSITORY:-${HOME}/Library/CloudStorage/OneDrive-Personligt/Filer/Projektbackups/restic-repository}"
KEYCHAIN_SERVICE="${PROJECT_BACKUP_KEYCHAIN_SERVICE:-dk.froekjaer.timelapse.project-backup.restic}"

usage() {
  cat <<'EOF'
Usage:
  project_snapshot_restore.sh --list
  project_snapshot_restore.sh --snapshot <id|latest> --target <empty-directory>
  project_snapshot_restore.sh --source onedrive --list
  project_snapshot_restore.sh --source onedrive --snapshot <id|latest> --target <empty-directory>

The restore target must be a new or empty directory. The active project tree is
never a valid target, preventing an accidental overwrite of current work.
EOF
}

MODE=""
SNAPSHOT=""
TARGET=""
SOURCE="local"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --list) MODE="list" ;;
    --snapshot) SNAPSHOT="${2:-}"; shift ;;
    --target) TARGET="${2:-}"; shift ;;
    --source) SOURCE="${2:-}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

case "$SOURCE" in
  local) ;;
  onedrive) RESTIC_REPOSITORY="$ONEDRIVE_REPOSITORY" ;;
  *) echo "Unknown restore source: $SOURCE" >&2; exit 2 ;;
esac

[[ -d "$RESTIC_REPOSITORY" ]] || { echo "Local backup repository is unavailable: $RESTIC_REPOSITORY" >&2; exit 1; }
command -v restic >/dev/null || { echo "restic is not installed" >&2; exit 1; }
export RESTIC_REPOSITORY
export RESTIC_PASSWORD_COMMAND="/usr/bin/security find-generic-password -a '${USER}' -s '${KEYCHAIN_SERVICE}' -w"

if [[ "$MODE" == "list" ]]; then
  restic snapshots --tag project-workspace
  exit 0
fi

[[ -n "$SNAPSHOT" && -n "$TARGET" ]] || { usage >&2; exit 2; }
ACTIVE_PROJECTS="${DATA_ROOT}/peter-home/projects"
TARGET="$(cd "$(dirname "$TARGET")" 2>/dev/null && pwd)/$(basename "$TARGET")"
[[ "$TARGET" != "$ACTIVE_PROJECTS" && "$TARGET" != "$ACTIVE_PROJECTS/"* ]] || {
  echo "Refusing to restore into the active project tree: $ACTIVE_PROJECTS" >&2
  exit 1
}

if [[ -e "$TARGET" ]] && [[ -n "$(find "$TARGET" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "Restore target must be empty: $TARGET" >&2
  exit 1
fi
mkdir -p "$TARGET"
restic restore "$SNAPSHOT" --target "$TARGET"
echo "Restore completed at: $TARGET"
