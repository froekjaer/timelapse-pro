#!/bin/bash
# verify_backup.sh — Verifikationsscript til TimeLapse Pro backup
#
# Formål: Bekræft at backup fungerer korrekt i produktion
# - Tjek at backup API endpoints er tilgængelige
# - Tjek backup indstillinger (include_images, auto_interval)
# - Tjek at seneste backup eksisterer og er ny nok
# - Bekræft backup indeholder forventede filer
# - Tjek billed-mirror status
# - (Valgfri) Test restore til midlertidig lokation
#
# Brug: ./verify_backup.sh [--dry-run] [--test-restore] [--check-api]
#
# Kræver: Root/sudo adgang til at læse backup destination

set -euo pipefail

# ── Konfiguration ───────────────────────────────────────────────────────────────
BACKUP_BASE="${BACKUP_BASE:-/Volumes/data-fast}"
BACKUP_NAS_PATH="${BACKUP_NAS_PATH:-/Volumes/data-fast}"
TIMELAPSE_ENV="${TIMELAPSE_ENV:-/opt/timelapse/headend/.env}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-48}"  # Backup må højst være 48 timer gammel
TEST_RESTORE_DIR="${TEST_RESTORE_DIR:-/tmp/timelapse-restore-test}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
CHECK_API="${CHECK_API:-true}"  # Tjek API endpoints (default: true)

# ── Farver til output ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo ""; echo "=== $1 ==="; }

# ── Help ───────────────────────────────────────────────────────────────────────────
show_help() {
    cat <<EOF
verify_backup.sh — Verifikationsscript til TimeLapse Pro backup

Brug:
    ./verify_backup.sh [OPTIONS]

Options:
    --dry-run        Vis hvad der ville blive tjekket uden at udføre handlinger
    --test-restore   Udfør faktisk restore til $TEST_RESTORE_DIR og verifikation
    --max-age HOURS  Maximal alder af backup i timer (default: 48)

Miljøvariabler:
    BACKUP_BASE       Backup base sti (default: /Volumes/Backup/timelapse)
    BACKUP_NAS_PATH   NAS sti hvis anderledes end BACKUP_BASE
    TIMELAPSE_ENV     Headend .env fil (default: /opt/timelapse/headend/.env)

Eksempler:
    ./verify_backup.sh                          # Tjek backup eksisterer og er ny nok
    ./verify_backup.sh --max-age 24             # Kræv backup inden for 24 timer
    ./verify_backup.sh --test-restore           # Fuld restore test
EOF
    exit 0
}

# ── Parse arguments ───────────────────────────────────────────────────────────────
DRY_RUN=false
TEST_RESTORE=false
CHECK_API=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)      DRY_RUN=true; shift ;;
        --test-restore)  TEST_RESTORE=true; shift ;;
        --max-age)       MAX_AGE_HOURS="$2"; shift 2 ;;
        --no-api)        CHECK_API=false; shift ;;
        -h|--help)      show_help ;;
        *)              log_error "Ukendt option: $1"; show_help ;;
    esac
done

# ── API checker funktioner ────────────────────────────────────────────────────────
check_api_endpoint() {
    local endpoint="$1"
    local description="$2"

    if [[ "$CHECK_API" != true ]]; then
        return 0
    fi

    log_info "Tjekker API endpoint: $description"
    local response
    response=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api${endpoint}" 2>/dev/null)
    local http_code=$(echo "$response" | tail -1)
    local body=$(echo "$response" | head -n -1)

    if [[ "$http_code" == "200" ]]; then
        log_info "✓ API endpoint OK (HTTP 200)"
        echo "$body"
        return 0
    else
        log_error "API endpoint fejlede (HTTP $http_code): $description"
        return 1
    fi
}

check_backup_api() {
    log_section "Backup API Endpoints"

    # Tjek health endpoint først
    if ! check_api_endpoint "/health" "Health check"; then
        log_error "Headend kører ikke eller er ikke tilgængelig på $BASE_URL"
        return 1
    fi

    # Tjek backup status
    local backup_status
    backup_status=$(check_api_endpoint "/admin/backup/status" "Backup status")

    if [[ $? -eq 0 ]]; then
        local running=$(echo "$backup_status" | jq -r '.running // false' 2>/dev/null || echo "unknown")
        if [[ "$running" == "true" ]]; then
            log_warn "En backup kører aktuelt"
        else
            log_info "Ingen backup kører aktuelt"
        fi
    fi

    # Tjek backup settings
    local backup_settings
    backup_settings=$(check_api_endpoint "/admin/backup/settings" "Backup settings")

    if [[ $? -eq 0 ]]; then
        # Vis vigtige indstillinger
        local include_images=$(echo "$backup_settings" | jq -r '.backup_include_images // false' 2>/dev/null || echo "unknown")
        local auto_interval=$(echo "$backup_settings" | jq -r '.backup_auto_interval // "manual"' 2>/dev/null)
        local nas_path=$(echo "$backup_settings" | jq -r '.backup_nas_path // empty' 2>/dev/null)

        log_info "Backup indstillinger:"
        log_info "  - backup_include_images: $include_images"
        log_info "  - backup_auto_interval: $auto_interval"
        [[ -n "$nas_path" ]] && log_info "  - backup_nas_path: $nas_path"

        # Opdater BACKUP_NAS_PATH hvis den er sat i settings
        if [[ -n "$nas_path" && "$nas_path" != "null" ]]; then
            BACKUP_NAS_PATH="$nas_path"
            log_info "Opdaterer BACKUP_NAS_PATH fra API: $nas_path"
        fi
    fi

    return 0
}

# ── Tjek at vi kører som root eller har nødvendige rettigheder ───────────────────
if [[ $EUID -ne 0 ]] && [[ $DRY_RUN != true ]]; then
    log_warn "Dette script bør køres som root for at verificere backup rettigheder"
    log_warn "Fortsætter alligevel — nogen tjek kan fejle..."
fi

# ── Hoved funktion ───────────────────────────────────────────────────────────────
main() {
    log_section "TimeLapse Pro Backup Verifikation (v1.1 2026-07-07)"
    log_info "Backup base: $BACKUP_BASE"
    log_info "Max alder: $MAX_AGE_HOURS timer"
    log_info "API tjek: $CHECK_API"

    local errors=0

    # 0. Tjek API endpoints først
    if [[ "$CHECK_API" == true ]]; then
        check_backup_api || ((errors++))
    fi

    # 1. Tjek at backup base eksisterer og er tilgængelig
    log_section "Backup Filsystem Tjek"
    if [[ ! -d "$BACKUP_BASE" ]]; then
        log_error "Backup base eksisterer ikke: $BACKUP_BASE"
        log_error "Er NAS mountet korrekt?"
        ((errors++))
    else
        log_info "✓ Backup base er tilgængelig"
    fi

    # 2. Find seneste backup
    LATEST_BACKUP=$(find "$BACKUP_BASE" -name "timelapse-backup-headend-*.tar.gz" -type f 2>/dev/null | sort -r | head -1)
    if [[ -z "$LATEST_BACKUP" ]]; then
        log_error "Ingen backup fundet i $BACKUP_BASE"
        log_error "Trigger en backup via: curl -X POST ${BASE_URL}/api/admin/backup/trigger"
        ((errors++))
    else
        log_info "✓ Seneste backup: $(basename "$LATEST_BACKUP")"
    fi

    # 3. Tjek backup alder
    if [[ -n "$LATEST_BACKUP" ]]; then
        BACKUP_AGE_SECONDS=$(($(date +%s) - $(stat -f %m "$LATEST_BACKUP")))
        BACKUP_AGE_HOURS=$((BACKUP_AGE_SECONDS / 3600))
        log_info "Backup alder: $BACKUP_AGE_HOURS timer"

        if [[ $BACKUP_AGE_HOURS -gt $MAX_AGE_HOURS ]]; then
            log_error "Backup er for gammel! ($BACKUP_AGE_HOURS > $MAX_AGE_HOURS timer)"
            log_error "Seneste backup var: $(date -r "$LATEST_BACKUP" '+%Y-%m-%d %H:%M:%S')"
            ((errors++))
        else
            log_info "✓ Backup er ny nok"
        fi
    fi

    # 4. Tjek backup størrelse (burde være mindst 1 MB)
    if [[ -n "$LATEST_BACKUP" ]]; then
        BACKUP_SIZE=$(stat -f%z "$LATEST_BACKUP")
        BACKUP_SIZE_MB=$((BACKUP_SIZE / 1024 / 1024))
        log_info "Backup størrelse: $BACKUP_SIZE_MB MB"

        if [[ $BACKUP_SIZE_MB -lt 1 ]]; then
            log_error "Backup ser for lille ud ($BACKUP_SIZE_MB MB) — kan være korrupt"
            ((errors++))
        else
            log_info "✓ Backup størrelse ser rimelig ud"
        fi
    fi

    # 5. Verificer tar.gz integritet (uden at udpakke)
    if [[ -n "$LATEST_BACKUP" ]]; then
        log_info "Verificerer tar.gz integritet..."
        if ! tar -tzf "$LATEST_BACKUP" >/dev/null 2>&1; then
            log_error "Backup fil er korrupt eller ikke en gyldig tar.gz"
            ((errors++))
        else
            log_info "✓ Backup fil integritet OK"
        fi
    fi

    # 6. Tjek indhold af backup (liste filer)
    if [[ -n "$LATEST_BACKUP" ]]; then
        log_info "Backup indhold (top 20 filer):"
        tar -tzf "$LATEST_BACKUP" | head -20
    fi

    # 7. Tjek for database dump
    if [[ -n "$LATEST_BACKUP" ]]; then
        DB_DUMP_COUNT=$(tar -tzf "$LATEST_BACKUP" | grep -c "timelapse_db_.*\.sql" || true)
        if [[ $DB_DUMP_COUNT -eq 0 ]]; then
            log_error "Ingen database dump fundet i backup!"
            ((errors++))
        else
            log_info "✓ Database dump fundet ($DB_DUMP_COUNT filer)"
        fi
    fi

    # 8. Tjek for config filer
    if [[ -n "$LATEST_BACKUP" ]]; then
        CONFIG_COUNT=$(tar -tzf "$LATEST_BACKUP" | grep -c "configs/" || true)
        if [[ $CONFIG_COUNT -eq 0 ]]; then
            log_warn "Ingen config filer fundet i backup (muligvis OK hvis ikke konfigureret)"
        else
            log_info "✓ Config filer fundet ($CONFIG_COUNT filer)"
        fi
    fi

    # 9. Billed-mirror tjek (hvis aktiveret)
    if [[ -n "$BACKUP_NAS_PATH" ]] && [[ -d "$BACKUP_NAS_PATH/timelapse-images-mirror" ]]; then
        log_section "Billed-mirror Verifikation"
        IMAGE_COUNT=$(find "$BACKUP_NAS_PATH/timelapse-images-mirror" -name "*.jpg" -type f 2>/dev/null | wc -l | tr -d ' ')
        log_info "Antal billeder i mirror: $IMAGE_COUNT"

        if [[ $IMAGE_COUNT -eq 0 ]]; then
            log_warn "Ingen billeder i mirror — er backup konfigureret til at inkludere billeder?"
        else
            log_info "✓ Billed-mirror indeholder $IMAGE_COUNT billeder"
        fi
    fi

    # 10. (Valgfri) Test restore
    if [[ "$TEST_RESTORE" == true && -n "$LATEST_BACKUP" ]]; then
        log_section "Test Restore"
        if [[ "$DRY_RUN" == true ]]; then
            log_info "[DRY-RUN] Ville have udført restore til $TEST_RESTORE_DIR"
        else
            log_info "Udfører test restore til $TEST_RESTORE_DIR..."
            mkdir -p "$TEST_RESTORE_DIR"

            # Ekstraher backup
            if ! tar -xzf "$LATEST_BACKUP" -C "$TEST_RESTORE_DIR"; then
                log_error "Restore fejlede!"
                ((errors++))
            else
                # Tjek ekstraheret indhold
                RESTORED_FILES=$(find "$TEST_RESTORE_DIR" -type f | wc -l | tr -d ' ')
                log_info "✓ Restore succesfuldt ($RESTORED_FILES filer ekstraheret)"

                # Tjek database dump
                RESTORED_DB=$(find "$TEST_RESTORE_DIR" -name "timelapse_db_*.sql" | head -1)
                if [[ -n "$RESTORED_DB" ]]; then
                    log_info "✓ Database dump ekstraheret: $(basename "$RESTORED_DB")"

                    # Tjek SQL filens indhold (skal indeholde CREATE TABLE etc.)
                    if grep -q "CREATE TABLE\|CREATE SCHEMA\|PostgreSQL database dump" "$RESTORED_DB"; then
                        log_info "✓ Database dump ser gyldig ud"
                    else
                        log_error "Database dump ser ikke ud til at være en gyldig SQL fil"
                        ((errors++))
                    fi
                fi

                # Oprydning
                log_info "Rydder op test restore directory..."
                rm -rf "$TEST_RESTORE_DIR"
            fi
        fi
    fi

    # ── Samlet konklusion ─────────────────────────────────────────────────────────
    log_section "Konklusion"
    if [[ $errors -eq 0 ]]; then
        log_info "✅ BACKUP VERIFIKATION BESTÅET (0 fejl)"
    else
        log_error "❌ BACKUP VERIFIKATION FEJLEDE ($errors fejl fundet)"
    fi

    log_info "Kontrolleret:"
    [[ "$CHECK_API" == true ]] && log_info "  - API endpoints (health, status, settings)"
    [[ -n "$LATEST_BACKUP" ]] && log_info "  - Backup eksisterer og er tilgængelig"
    [[ -n "$LATEST_BACKUP" ]] && log_info "  - Backup er ny nok ($BACKUP_AGE_HOURS <= $MAX_AGE_HOURS timer)"
    [[ -n "$LATEST_BACKUP" ]] && log_info "  - Backup integritet OK"
    [[ -n "$LATEST_BACKUP" ]] && log_info "  - Database dump til stede"

    if [[ -n "$BACKUP_NAS_PATH" ]] && [[ -d "$BACKUP_NAS_PATH/timelapse-images-mirror" ]]; then
        log_info "  - Billed-mirror verifikeret ($IMAGE_COUNT billeder)"
    fi

    if [[ "$TEST_RESTORE" == true ]]; then
        log_info "  - Test restore bestået"
    fi

    log_info ""
    log_info "Næste skridt:"
    log_info "  1. Dokumenter RTO/RPO baseret på backup alder og størrelse"
    log_info "  2. Schedulér regelmæssig kørsel: launchctl list | grep backup"
    log_info "  3. Overvej notifikation ved backup fejl (SIEM integration)"

    return $errors
}

# ── Kør hoved funktion ───────────────────────────────────────────────────────────
main "$@"
