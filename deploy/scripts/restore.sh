#!/bin/bash
# restore.sh — TimeLapse Pro Headend Restore Script
#
# Purpose: Restore from backup created by backup.sh
# Usage: ./restore.sh <backup-file> [--options]
#
# Environment variables:
#   BACKUP_BASE         Backup source directory (default: /Volumes/data-fast)
#   TIMELAPSE_ENV       Path to .env file (default: /opt/timelapse/headend/.env)
#
# Requirements:
#   - psql (PostgreSQL client tools)
#   - OpenSSL (for decryption, if backup is encrypted)
#   - tar, gzip for archive extraction
#
# Author: TimeLapse Pro
# Version: 1.0.0
# Date: 2026-07-07

set -euo pipefail

# ── Configuration ───────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_BASE="${BACKUP_BASE:-/Volumes/data-fast}"
TIMELAPSE_ENV="${TIMELAPSE_ENV:-/opt/timelapse/headend/.env}"
DECRYPTION_KEY="${DECRYPTION_KEY:-}"
RESTORE_TEMP_DIR="${RESTORE_TEMP_DIR:-/tmp/timelapse-restore-$$}"

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
restore.sh — TimeLapse Pro Headend Restore Script

Usage:
    ./restore.sh <backup-file> [OPTIONS]

Arguments:
    backup-file    Path to backup archive (.tar.gz or .tar.gz.enc)

Options:
    --decrypt              Decrypt backup using DECRYPTION_KEY
    --no-db               Skip database restore
    --no-configs          Skip config restore
    --no-images           Skip images restore
    --dry-run             Show what would be restored without making changes
    --verify-only         Verify backup integrity without restoring

Environment variables:
    DECRYPTION_KEY       Key for decryption (if backup is encrypted)
    TIMELAPSE_ENV        Path to .env file

Examples:
    ./restore.sh /path/to/timelapse-headend-20260707_120000.tar.gz
    ./restore.sh backup.tar.gz --decrypt
    ./restore.sh backup.tar.gz --verify-only
    ./restore.sh backup.tar.gz --dry-run

SAFETY: This script will modify your database and overwrite configs.
        Use --dry-run first to preview changes.

EOF
    exit 0
}

# ── Parse arguments ─────────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    log_error "Missing backup file argument"
    show_help
fi

BACKUP_FILE="$1"
SKIP_DB=false
SKIP_CONFIGS=false
SKIP_IMAGES=false
DRY_RUN=false
VERIFY_ONLY=false
DECRYPT=false

shift
while [[ $# -gt 0 ]]; do
    case $1 in
        --decrypt)     DECRYPT=true; shift ;;
        --no-db)       SKIP_DB=true; shift ;;
        --no-configs)  SKIP_CONFIGS=true; shift ;;
        --no-images)   SKIP_IMAGES=true; shift ;;
        --dry-run)     DRY_RUN=true; shift ;;
        --verify-only) VERIFY_ONLY=true; shift ;;
        -h|--help)     show_help ;;
        *)             log_error "Unknown option: $1"; show_help ;;
    esac
done

# ── Validate backup file ──────────────────────────────────────────────────────
log_section "Validating Backup"

if [[ ! -f "$BACKUP_FILE" ]]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

log_info "Backup file: $BACKUP_FILE"
FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log_info "File size: $FILE_SIZE"

# Check for metadata file
META_FILE="${BACKUP_FILE}.meta"
if [[ -f "$META_FILE" ]]; then
    log_info "Metadata found:"
    cat "$META_FILE" | sed 's/^/  /'
else
    log_warn "Metadata file not found: $META_FILE"
fi

# Check checksum
SHA256_FILE="${BACKUP_FILE}.sha256"
if [[ -f "$SHA256_FILE" ]]; then
    EXPECTED_SHA256=$(cat "$SHA256_FILE" | cut -d ' ' -f1)
    ACTUAL_SHA256=$(shasum -a 256 "$BACKUP_FILE" | cut -d ' ' -f1)

    if [[ "$EXPECTED_SHA256" == "$ACTUAL_SHA256" ]]; then
        log_info "SHA256 verified: $ACTUAL_SHA256"
    else
        log_error "SHA256 mismatch!"
        log_error "Expected: $EXPECTED_SHA256"
        log_error "Actual:   $ACTUAL_SHA256"
        exit 1
    fi
else
    log_warn "Checksum file not found"
fi

if [[ "$VERIFY_ONLY" == true ]]; then
    log_info "Backup verification complete"
    exit 0
fi

# ── Decrypt if needed ─────────────────────────────────────────────────────────
if [[ "$BACKUP_FILE" == *.enc ]]; then
    if [[ "$DECRYPT" == true && -n "$DECRYPTION_KEY" ]]; then
        log_section "Decrypting Backup"
        DECRYPTED_FILE="${BACKUP_FILE%.enc}"

        if [[ "$DRY_RUN" == true ]]; then
            log_info "Would decrypt to: $DECRYPTED_FILE"
            BACKUP_FILE="$DECRYPTED_FILE"
        else
            if openssl enc -aes-256-cbc -d -pbkdf2 \
                -in "$BACKUP_FILE" \
                -out "$DECRYPTED_FILE" \
                -k "$DECRYPTION_KEY"; then
                log_info "Decryption complete"
                BACKUP_FILE="$DECRYPTED_FILE"
            else
                log_error "Decryption failed"
                exit 1
            fi
        fi
    else
        log_error "Backup is encrypted but --decrypt not provided"
        log_error "Use: --decrypt with DECRYPTION_KEY environment variable"
        exit 1
    fi
fi

# ── Extract archive ───────────────────────────────────────────────────────────
log_section "Extracting Archive"

if [[ "$DRY_RUN" == true ]]; then
    log_info "Would extract archive to: $RESTORE_TEMP_DIR"
else
    mkdir -p "$RESTORE_TEMP_DIR"

    if tar -xzf "$BACKUP_FILE" -C "$RESTORE_TEMP_DIR"; then
        log_info "Archive extracted successfully"
    else
        log_error "Failed to extract archive"
        rm -rf "$RESTORE_TEMP_DIR"
        exit 1
    fi

    # Verify structure
    if [[ ! -d "$RESTORE_TEMP_DIR/database" && ! -d "$RESTORE_TEMP_DIR/configs" ]]; then
        log_error "Invalid backup structure (missing database/configs directories)"
        rm -rf "$RESTORE_TEMP_DIR"
        exit 1
    fi
fi

# ── Database restore ─────────────────────────────────────────────────────────
if [[ "$SKIP_DB" == false ]]; then
    log_section "Database Restore"

    SQL_FILE=$(find "$RESTORE_TEMP_DIR/database" -name "*.sql" 2>/dev/null | head -1)

    if [[ -z "$SQL_FILE" ]]; then
        log_error "No SQL file found in backup"
    elif [[ "$DRY_RUN" == true ]]; then
        log_info "Would restore database from: $SQL_FILE"
    else
        # Load database connection from .env
        if [[ -f "$TIMELAPSE_ENV" ]]; then
            while IFS='=' read -r key value; do
                [[ "$key" =~ ^#.*$ ]] && continue
                [[ -z "$key" ]] && continue
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
        DB_HOST=$(echo "$BACKUP_DB_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
        DB_PORT=$(echo "$BACKUP_DB_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        DB_NAME=$(echo "$BACKUP_DB_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
        DB_USER=$(echo "$BACKUP_DB_URL" | sed -n 's/\/\/\([^:]*\):.*/\1/p')

        DB_HOST="${DB_HOST:-localhost}"
        DB_PORT="${DB_PORT:-5432}"
        DB_NAME="${DB_NAME:-timelapse_db}"
        DB_USER="${DB_USER:-timelapse}"

        # Check psql exists
        if ! command -v psql &> /dev/null; then
            # Try Homebrew path
            PSQL="/opt/homebrew/bin/psql"
            if [[ ! -f "$PSQL" ]]; then
                log_error "psql not found. Install PostgreSQL client tools:"
                log_error "  brew install postgresql"
                exit 1
            fi
        else
            PSQL="psql"
        fi

        # Safety confirmation
        log_warn "This will DROP and recreate database: $DB_NAME"
        echo -n "Type 'yes' to confirm: "
        read -r CONFIRM

        if [[ "$CONFIRM" != "yes" ]]; then
            log_info "Restore cancelled by user"
            rm -rf "$RESTORE_TEMP_DIR"
            exit 0
        fi

        # Restore database
        log_info "Dropping existing database..."
        "$PSQL" -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
            -c "DROP DATABASE IF EXISTS ${DB_NAME};" postgres || log_warn "Failed to drop database"

        log_info "Creating database..."
        "$PSQL" -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
            -c "CREATE DATABASE ${DB_NAME};" postgres || log_error "Failed to create database"

        log_info "Restoring from SQL dump..."
        if PGPASSWORD="${DB_PASSWORD:-}" "$PSQL" -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
            -f "$SQL_FILE" "$DB_NAME" > "$RESTORE_TEMP_DIR/psql.log" 2>&1; then
            log_info "Database restored successfully"
        else
            log_error "Database restore failed. Check log:"
            cat "$RESTORE_TEMP_DIR/psql.log" | tail -20
            rm -rf "$RESTORE_TEMP_DIR"
            exit 1
        fi
    fi
fi

# ── Config restore ───────────────────────────────────────────────────────────
if [[ "$SKIP_CONFIGS" == false ]]; then
    log_section "Config Restore"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "Would restore configs from: $RESTORE_TEMP_DIR/configs"
        find "$RESTORE_TEMP_DIR/configs" -type f 2>/dev/null | sed 's/^/  /'
    else
        for config_file in "$RESTORE_TEMP_DIR/configs"/*; do
            [[ -f "$config_file" ]] || continue

            filename=$(basename "$config_file")

            # Determine destination
            case "$filename" in
                headend.env)
                    dest="/opt/timelapse/headend/.env"
                    ;;
                nginx.conf)
                    dest="/opt/homebrew/etc/nginx/nginx.conf"
                    ;;
                timelapse-headend.plist)
                    dest="/Library/LaunchDaemons/timelapse-headend.plist"
                    ;;
                headend_poller.sh)
                    dest="/opt/timelapse/deploy/headend_poller.sh"
                    ;;
                *)
                    log_warn "Unknown config file: $filename"
                    continue
                    ;;
            esac

            log_info "Restoring: $filename → $dest"

            # Backup existing file
            if [[ -f "$dest" ]]; then
                cp "$dest" "${dest}.backup-$(date +%Y%m%d_%H%M%S)"
                log_info "  Existing file backed up"
            fi

            # Copy file
            cp "$config_file" "$dest"
            log_info "  Restored"
        done

        log_info "Config restore complete"
        log_info "You may need to restart services:"
        log_info "  sudo launchctl kickstart -k system/timelapse-headend"
        log_info "  sudo brew services restart nginx"
    fi
fi

# ── Images restore ───────────────────────────────────────────────────────────
if [[ "$SKIP_IMAGES" == false && -d "$RESTORE_TEMP_DIR/captures" ]]; then
    log_section "Images/Captures Restore"

    if [[ "$DRY_RUN" == true ]]; then
        log_info "Would restore captures to: /Volumes/data-fast/timelapse-images"
    else
        DEST_PATH="/Volumes/data-fast/timelapse-images"

        if [[ ! -d "$DEST_PATH" ]]; then
            log_warn "Destination path does not exist: $DEST_PATH"
            log_info "Creating directory..."
            mkdir -p "$DEST_PATH"
        fi

        log_info "Restoring captures..."
        rsync -a --progress "$RESTORE_TEMP_DIR/captures/" "$DEST_PATH/"
        log_info "Captures restored"
    fi
fi

# ── Cleanup ─────────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == false ]]; then
    log_section "Cleanup"
    log_info "Removing temporary files..."
    rm -rf "$RESTORE_TEMP_DIR"

    # Remove decrypted file if it was created
    if [[ "$DECRYPT" == true && -f "${BACKUP_FILE%.enc}" ]]; then
        rm -f "${BACKUP_FILE%.enc}"
    fi
fi

log_section "Restore Complete"
log_info "Backup: $BACKUP_FILE"
log_info "Status: Restored successfully"

if [[ "$DRY_RUN" == false ]]; then
    log_warn "Review restored configs and restart services as needed"
fi

exit 0
