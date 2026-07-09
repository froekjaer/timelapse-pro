#!/bin/bash
# backup.sh — TimeLapse Pro Headend Backup Script
#
# Purpose: Create backup of database, configs, and (optionally) captures
# Usage: ./backup.sh [--with-images] [--dry-run]
#
# Environment variables:
#   BACKUP_BASE         Backup destination (default: /Volumes/data-fast)
#   BACKUP_INCLUDE_IMAGES  Include captures in backup (default: false)
#   TIMELAPSE_ENV       Path to .env file (default: /opt/timelapse/headend/.env)
#
# Requirements:
#   - pg_dump (PostgreSQL client tools)
#   - OpenSSL (for encryption, optional)
#   - tar, gzip for archive creation
#
# Author: TimeLapse Pro
# Version: 1.0.0
# Date: 2026-07-07

set -euo pipefail

# ── Configuration ───────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_BASE="${BACKUP_BASE:-/Volumes/data-fast}"
BACKUP_INCLUDE_IMAGES="${BACKUP_INCLUDE_IMAGES:-false}"
TIMELAPSE_ENV="${TIMELAPSE_ENV:-/opt/timelapse/headend/.env}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
ENCRYPT_BACKUP="${ENCRYPT_BACKUP:-false}"
ENCRYPTION_KEY="${ENCRYPTION_KEY:-}"
BACKUP_NAME="timelapse-headend-$(date +%Y%m%d_%H%M%S)"
LOCK_FILE="/tmp/timelapse-backup.lock"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo ""; echo -e "${BLUE}=== $1 ===${NC}"; }

# ── Help ───────────────────────────────────────────────────────────────────────
show_help() {
    cat <<EOF
backup.sh — TimeLapse Pro Headend Backup Script

Usage:
    ./backup.sh [OPTIONS]

Options:
    --with-images    Include captures/images in backup
    --dry-run        Show what would be backed up without creating files
    --encrypt        Encrypt backup using OpenSSL (requires ENCRYPTION_KEY)
    --no-db          Skip database backup
    --no-configs     Skip config backup

Environment variables:
    BACKUP_BASE              Backup destination (default: /Volumes/data-fast)
    BACKUP_INCLUDE_IMAGES    Include captures (default: false)
    BACKUP_RETENTION_DAYS    Days to keep old backups (default: 30)
    ENCRYPTION_KEY          Base64-encoded key for encryption
    TIMELAPSE_ENV           Path to .env file

Examples:
    ./backup.sh                           # Database + configs only
    ./backup.sh --with-images              # Full backup including images
    ./backup.sh --encrypt                  # Encrypted backup
    ./backup.sh --dry-run                  # Preview mode

EOF
    exit 0
}

# ── Parse arguments ─────────────────────────────────────────────────────────────
DRY_RUN=false
SKIP_DB=false
SKIP_CONFIGS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --with-images) BACKUP_INCLUDE_IMAGES=true; shift ;;
        --dry-run)     DRY_RUN=true; shift ;;
        --encrypt)     ENCRYPT_BACKUP=true; shift ;;
        --no-db)       SKIP_DB=true; shift ;;
        --no-configs)  SKIP_CONFIGS=true; shift ;;
        -h|--help)     show_help ;;
        *)             log_error "Unknown option: $1"; show_help ;;
    esac
done

# ── Lock file ───────────────────────────────────────────────────────────────────
if [[ -f "$LOCK_FILE" ]]; then
    log_warn "Backup already running (lock file exists: $LOCK_FILE)"
    log_info "If this is incorrect, remove the lock file:"
    log_info "  rm $LOCK_FILE"
    exit 1
fi
trap 'rm -f "$LOCK_FILE"' EXIT
echo "$$" > "$LOCK_FILE"

# ── Create backup directory ─────────────────────────────────────────────────────
BACKUP_DIR="$BACKUP_BASE/backups/$BACKUP_NAME"

if [[ "$DRY_RUN" == true ]]; then
    log_section "DRY RUN MODE"
    log_info "Would create backup directory: $BACKUP_DIR"
else
    mkdir -p "$BACKUP_DIR"
    log_info "Backup directory: $BACKUP_DIR"
fi

# ── Database backup ─────────────────────────────────────────────────────────────
if [[ "$SKIP_DB" == false ]]; then
    log_section "Database Backup"

    # Load database connection from .env
    if [[ -f "$TIMELAPSE_ENV" ]]; then
        # Source .env file (carefully)
        while IFS='=' read -r key value; do
            # Skip comments and empty lines
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            # Remove leading/trailing whitespace
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)
            export "$key=$value"
        done < "$TIMELAPSE_ENV"
    fi

    DB_URL="${DATABASE_URL:-}"
    BACKUP_DB_URL="${BACKUP_DATABASE_URL:-$DB_URL}"

    if [[ -z "$BACKUP_DB_URL" ]]; then
        log_error "DATABASE_URL or BACKUP_DATABASE_URL not set"
        exit 1
    fi

    # Parse DATABASE_URL
    # Format: postgresql://user:password@host:port/database
    DB_HOST=$(echo "$BACKUP_DB_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo "$BACKUP_DB_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_NAME=$(echo "$BACKUP_DB_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
    DB_USER=$(echo "$BACKUP_DB_URL" | sed -n 's/\/\/\([^:]*\):.*/\1/p')

    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
    DB_NAME="${DB_NAME:-timelapse_db}"
    DB_USER="${DB_USER:-timelapse}"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "Would backup database:"
        log_info "  Host: $DB_HOST:$DB_PORT"
        log_info "  Database: $DB_NAME"
        log_info "  User: $DB_USER"
    else
        # Check pg_dump exists
        if ! command -v pg_dump &> /dev/null; then
            # Try Homebrew path
            PG_DUMP="/opt/homebrew/bin/pg_dump"
            if [[ ! -f "$PG_DUMP" ]]; then
                log_error "pg_dump not found. Install PostgreSQL client tools:"
                log_error "  brew install postgresql"
                exit 1
            fi
        else
            PG_DUMP="pg_dump"
        fi

        # Run pg_dump
        log_info "Running pg_dump..."
        SQL_FILE="$BACKUP_DIR/database/timelapse_db_$(date +%Y%m%d_%H%M%S).sql"

        mkdir -p "$(dirname "$SQL_FILE")"

        PG_DUMP_CMD=(
            "$PG_DUMP"
            -h "$DB_HOST"
            -p "$DB_PORT"
            -U "$DB_USER"
            --no-password
            --enable-row-security
            "$DB_NAME"
        )

        # Set PGPASSFILE or use .pgpass
        if [[ "$DB_PASSWORD" ]]; then
            export PGPASSWORD="$DB_PASSWORD"
        fi

        if "${PG_DUMP_CMD[@]}" > "$SQL_FILE" 2> "$SQL_FILE.err"; then
            SQL_SIZE=$(du -h "$SQL_FILE" | cut -f1)
            log_info "Database backup complete: $SQL_FILE ($SQL_SIZE)"
            rm -f "$SQL_FILE.err"
        else
            log_error "pg_dump failed:"
            cat "$SQL_FILE.err" >&2
            rm -f "$SQL_FILE" "$SQL_FILE.err"
            exit 1
        fi

        unset PGPASSWORD
    fi
fi

# ── Config backup ─────────────────────────────────────────────────────────────
if [[ "$SKIP_CONFIGS" == false ]]; then
    log_section "Config Backup"

    CONFIG_ITEMS=(
        "/opt/timelapse/headend/.env:headend.env"
        "/opt/homebrew/etc/nginx/nginx.conf:nginx.conf"
        "/Library/LaunchDaemons/timelapse-headend.plist:timelapse-headend.plist"
        "/opt/timelapse/deploy/headend_poller.sh:headend_poller.sh"
        "$PROJECT_ROOT/deploy:deploy-scripts"
    )

    if [[ "$DRY_RUN" == true ]]; then
        log_info "Would backup configs:"
        for item in "${CONFIG_ITEMS[@]}"; do
            src="${item%%:*}"
            log_info "  - $src"
        done
    else
        mkdir -p "$BACKUP_DIR/configs"

        for item in "${CONFIG_ITEMS[@]}"; do
            src="${item%%:*}"
            dest_name="${item##*:}"

            if [[ -d "$src" ]]; then
                log_info "Copying directory: $src"
                cp -R "$src" "$BACKUP_DIR/configs/$dest_name" 2>/dev/null || log_warn "  Skipped: $src"
            elif [[ -f "$src" ]]; then
                log_info "Copying file: $src"
                cp "$src" "$BACKUP_DIR/configs/$dest_name" 2>/dev/null || log_warn "  Skipped: $src"
            else
                log_warn "Not found: $src"
            fi
        done
    fi
fi

# ── Images/Captures backup ─────────────────────────────────────────────────────
if [[ "$BACKUP_INCLUDE_IMAGES" == true ]]; then
    log_section "Images/Captures Backup"

    IMAGE_PATHS=(
        "/Volumes/data-fast/timelapse-images"
        "/opt/timelapse/captures"
    )

    for path in "${IMAGE_PATHS[@]}"; do
        if [[ -d "$path" ]]; then
            if [[ "$DRY_RUN" == true ]]; then
                log_info "Would backup: $path"
            else
                log_info "Copying: $path"
                mkdir -p "$BACKUP_DIR/captures"
                # Use rsync for efficient copy
                rsync -a --progress "$path/" "$BACKUP_DIR/captures/" || log_warn "  Failed: $path"
            fi
        fi
    done
fi

# ── Create archive ─────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == false ]]; then
    log_section "Creating Archive"

    ARCHIVE_FILE="$BACKUP_BASE/backups/${BACKUP_NAME}.tar.gz"

    if [[ -d "$BACKUP_DIR" ]]; then
        log_info "Compressing backup..."
        tar -czf "$ARCHIVE_FILE" -C "$BACKUP_DIR" . 2>/dev/null

        ARCHIVE_SIZE=$(du -h "$ARCHIVE_FILE" | cut -f1)
        log_info "Archive created: $ARCHIVE_FILE ($ARCHIVE_SIZE)"

        # Calculate checksum
        SHA256=$(shasum -a 256 "$ARCHIVE_FILE" | cut -d ' ' -f1)
        echo "$SHA256" > "$ARCHIVE_FILE.sha256"
        log_info "SHA256: $SHA256"

        # Create metadata
        cat > "$ARCHIVE_FILE.meta" <<EOF
backup_name=$BACKUP_NAME
created=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
size=$ARCHIVE_SIZE
sha256=$SHA256
includes_db=$( [[ "$SKIP_DB" == false ]] && echo "true" || echo "false" )
includes_configs=$( [[ "$SKIP_CONFIGS" == false ]] && echo "true" || echo "false" )
includes_images=$BACKUP_INCLUDE_IMAGES
encrypted=false
EOF

        # Encryption (optional)
        if [[ "$ENCRYPT_BACKUP" == true && -n "$ENCRYPTION_KEY" ]]; then
            log_info "Encrypting backup..."
            openssl enc -aes-256-cbc -salt -pbkdf2 \
                -in "$ARCHIVE_FILE" \
                -out "${ARCHIVE_FILE}.enc" \
                -k "$ENCRYPTION_KEY"

            mv "${ARCHIVE_FILE}.enc" "$ARCHIVE_FILE"
            echo "encrypted=true" >> "$ARCHIVE_FILE.meta"
            log_info "Backup encrypted"
        fi

        # Remove temp directory
        rm -rf "$BACKUP_DIR"

        log_info "Backup complete: $ARCHIVE_FILE"
    else
        log_error "Backup directory not created"
        exit 1
    fi
fi

# ── Cleanup old backups ─────────────────────────────────────────────────────────
log_section "Cleanup Old Backups"

if [[ "$DRY_RUN" == true ]]; then
    log_info "Would remove backups older than $BACKUP_RETENTION_DAYS days"
else
    # Remove old backups
    find "$BACKUP_BASE/backups" -name "timelapse-headend-*.tar.gz" -mtime +${BACKUP_RETENTION_DAYS} -delete 2>/dev/null
    find "$BACKUP_BASE/backups" -name "timelapse-headend-*.tar.gz.*" -mtime +${BACKUP_RETENTION_DAYS} -delete 2>/dev/null

    REMAINING=$(find "$BACKUP_BASE/backups" -name "timelapse-headend-*.tar.gz" | wc -l)
    log_info "Remaining backups: $REMAINING"
fi

log_section "Backup Summary"
log_info "Backup: $BACKUP_NAME"
log_info "Status: Complete"
exit 0
