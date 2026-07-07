#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# verify_fail2ban.sh — Verifikation og setup af fail2ban til TimeLapse Pro
# Version: 1.0.1 | 2026-07-07
# ────────────────────────────────────────────────────────────────────────────────
# Tjekker at fail2ban er installeret, konfigureret og kører korrekt.
# Tilbyder at oprette basic TimeLapse Pro filtre hvis de mangler.
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Farver
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()     { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()   { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()  { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "\n${BLUE}═══ $1 ═══${NC}"; }

# Konfiguration
TIMELAPSE_PRO_CONFIG="/etc/fail2ban/jail.d/timelapse-pro.local"
TIMELAPSE_PRO_FILTER="/etc/fail2ban/filter.d/timelapse-pro.conf"
NGINX_ACCESS_LOG="/opt/homebrew/var/log/nginx/access.log"
MACOS_PFCTL_ANCHOR="/etc/pf.anchors/timelapse-pro"

# ── Tjek at fail2ban er installeret ───────────────────────────────────────────
check_fail2ban_installed() {
    log_section "1. Fail2ban Installation"

    if command -v fail2ban-client >/dev/null 2>&1; then
        log_ok "fail2ban er installeret"
        fail2ban-client --version 2>/dev/null || true
        return 0
    else
        log_error "fail2ban er IKKE installeret"
        log_info "Installer med: brew install fail2ban"
        return 1
    fi
}

# ── Tjek at fail2ban kører ───────────────────────────────────────────────────
check_fail2ban_running() {
    log_section "2. Fail2ban Status"

    if pgrep -x "fail2ban-server" >/dev/null 2>&1; then
        log_ok "fail2ban-server kører"
    else
        log_error "fail2ban-server kører IKKE"
        log_info "Start med: sudo brew services start fail2ban"
        return 1
    fi

    # Tjek status
    if command -v fail2ban-client >/dev/null 2>&1; then
        log_info "Fail2ban status:"
        sudo fail2ban-client status 2>/dev/null || true
    fi

    return 0
}

# ── Tjek at TimeLapse Pro jails eksisterer ───────────────────────────────────
check_timelapse_jails() {
    log_section "3. TimeLapse Pro Jails"

    local jails_found=0

    # Tjek for nginx jail
    if sudo fail2ban-client status nginx 2>/dev/null | grep -q "Status"; then
        log_ok "nginx jail er aktiv"
        jails_found=$((jails_found + 1))
    else
        log_warn "nginx jail mangler eller er inaktiv"
    fi

    # Tjek for sshd jail
    if sudo fail2ban-client status sshd 2>/dev/null | grep -q "Status"; then
        log_ok "sshd jail er aktiv"
        jails_found=$((jails_found + 1))
    else
        log_warn "sshd jail mangler eller er inaktiv"
    fi

    # Tjek for custom timelapse-api jail
    if sudo fail2ban-client status timelapse-api 2>/dev/null | grep -q "Status"; then
        log_ok "timelapse-api jail er aktiv"
        jails_found=$((jails_found + 1))
    else
        log_warn "timelapse-api jail mangler (custom TimeLapse Pro jail)"
    fi

    if [ $jails_found -eq 0 ]; then
        log_error "Ingen jails er aktive!"
        return 1
    fi

    log_info "Total aktive jails: $jails_found"
    return 0
}

# ── Tjek nginx log fil ─────────────────────────────────────────────────────────
check_nginx_logs() {
    log_section "4. Nginx Logs"

    if [ -f "$NGINX_ACCESS_LOG" ]; then
        log_ok "Nginx access log eksisterer: $NGINX_ACCESS_LOG"

        # Tjek seneste log linje
        local latest
        latest=$(tail -1 "$NGINX_ACCESS_LOG" 2>/dev/null || echo "")
        if [ -n "$latest" ]; then
            log_info "Seneste log linje: ${latest:0:100}..."
        fi
    else
        log_warn "Nginx access log ikke fundet: $NGINX_ACCESS_LOG"
        log_info "Søger efter alternativ placering..."

        local alt_log=$(find /opt/homebrew -name "access.log" -path "*/nginx/*" 2>/dev/null | head -1)
        if [ -n "$alt_log" ]; then
            log_info "Fundet alternativ: $alt_log"
        fi
    fi
}

# ── Vis aktive bans ───────────────────────────────────────────────────────────
show_active_bans() {
    log_section "5. Aktive Bans"

    if command -v fail2ban-client >/dev/null 2>&1; then
        log_info "Aktive IP bans per jail:"

        for jail in nginx sshd timelapse-api; do
            local banned
            banned=$(sudo fail2ban-client status "$jail" 2>/dev/null | grep "Banned IP list:" || true)
            if [ -n "$banned" ]; then
                echo "  [$jail]"
                echo "    $banned" | sed 's/Banned IP list:/IP:/g'
            fi
        done
    fi
}

# ── Vis fail2ban log ───────────────────────────────────────────────────────────
show_fail2ban_log() {
    log_section "6. Fail2ban Log"

    local log_file="/var/log/fail2ban.log"
    if [ ! -f "$log_file" ]; then
        # Check macOS Homebrew location
        log_file="/opt/homebrew/var/log/fail2ban.log"
    fi

    if [ -f "$log_file" ]; then
        log_ok "Fail2ban log: $log_file"
        log_info "Seneste 10 linjer:"
        tail -10 "$log_file" 2>/dev/null || true
    else
        log_warn "Fail2ban log ikke fundet"
    fi
}

# ── Hovedprogram ─────────────────────────────────────────────────────────────
show_usage() {
    echo "Brug: $0 [--apply] [--dry-run]"
    echo ""
    echo "Tilvalg:"
    echo "  --apply    Installer/opdater fail2ban config hvis den mangler"
    echo "  --dry-run  Vis hvad der ville blive installeret (uden at gøre det)"
    echo ""
    echo "Uden tilvalg: Kører kun verifikation"
}

apply_config() {
    log_section "A. Installerer TimeLapse Pro Fail2ban Config"

    local dry_run=false
    if [ "${1:-}" = "--dry-run" ]; then
        dry_run=true
        log_info "DRY-RUN MODE — ingen ændringer vil blive udført"
    fi

    # Tjek om config filer eksisterer
    local config_exists=false
    if [ -f "$TIMELAPSE_PRO_CONFIG" ] && [ -f "$TIMELAPSE_PRO_FILTER" ]; then
        config_exists=true
        log_warn "Config filer eksisterer allerede:"
        log_info "  - $TIMELAPSE_PRO_CONFIG"
        log_info "  - $TIMELAPSE_PRO_FILTER"
        echo ""
        read -p "Overskriv eksisterende config? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Springer over config installation"
            return 0
        fi
    fi

    # Generer pfctl anchor til macOS
    log_info "Genererer pfctl anchor til macOS..."
    local pfctl_content
    pfctl_content=$(cat <<'EOF'
# TimeLapse Pro pfctl anchor for fail2ban
# Tilføj til /etc/pf.conf:
#   anchor "timelapse-pro"
#   load anchor "timelapse-pro" from "/etc/pf.anchors/timelapse-pro"

table <timelapse-banned> persist
block quick from <timelapse-banned> to any label "timelapse-pro-fail2ban"
EOF
)

    if [ "$dry_run" = true ]; then
        echo "--- pfctl anchor (skal gemmes som $MACOS_PFCTL_ANCHOR) ---"
        echo "$pfctl_content"
        echo "---"
    else
        log_info "Opretter pfctl anchor: $MACOS_PFCTL_ANCHOR"
        sudo mkdir -p "$(dirname "$MACOS_PFCTL_ANCHOR")"
        echo "$pfctl_content" | sudo tee "$MACOS_PFCTL_ANCHOR" >/dev/null
        log_ok "pfctl anchor oprettet"
        log_warn "Husk at tilføje til /etc/pf.conf:"
        echo '  anchor "timelapse-pro"'
        echo '  load anchor "timelapse-pro" from "/etc/pf.anchors/timelapse-pro"'
    fi

    # Generer jail config
    log_info "Genererer jail config..."
    local jail_content
    jail_content=$(cat <<'EOF'
# TimeLapse Pro Fail2ban Jail Configuration
# Version: 1.0.1 | 2026-07-07

[nginx]
enabled   = true
port      = http,https
filter    = nginx
logpath   = /opt/homebrew/var/log/nginx/access.log
maxretry  = 5
findtime  = 600
bantime   = 3600
action    = pfctl[name=nginx, port=80,443]

[sshd]
enabled   = true
port      = ssh
filter    = sshd
logpath   = /var/log/system.log
maxretry  = 3
findtime  = 600
bantime   = 3600
action    = pfctl[name=SSH]

[timelapse-api]
enabled   = true
port      = http,https
filter    = timelapse-api
logpath   = /opt/homebrew/var/log/nginx/access.log
maxretry  = 10
findtime  = 600
bantime   = 7200
action    = pfctl[name=timelapse-api, port=80,443]
EOF
)

    if [ "$dry_run" = true ]; then
        echo "--- jail config (skal gemmes som $TIMELAPSE_PRO_CONFIG) ---"
        echo "$jail_content"
        echo "---"
    else
        log_info "Opretter jail config: $TIMELAPSE_PRO_CONFIG"
        sudo mkdir -p "$(dirname "$TIMELAPSE_PRO_CONFIG")"
        echo "$jail_content" | sudo tee "$TIMELAPSE_PRO_CONFIG" >/dev/null
        log_ok "Jail config oprettet"
    fi

    # Generer filter config
    log_info "Genererer filter config..."
    local filter_content
    filter_content=$(cat <<'EOF'
# TimeLapse Pro Fail2ban Filter Configuration
# Version: 1.0.1 | 2026-07-07

[Definition]
# Fail regex for TimeLapse Pro API
# Blokerer IPs med for mange failed login forsøg

failregex = ^<HOST> .* "(GET|POST|PUT|DELETE) /api/.*" 401 .*$
            ^<HOST> .* "(GET|POST|PUT|DELETE) /api/(auth/login|admin/.*|lab/.*)" 403 .*$

ignoreregex = ^<HOST> .* "(GET|POST) /api/health" 200
             ^<HOST> .* "GET /api/thumbnails/.*" 200
EOF
)

    if [ "$dry_run" = true ]; then
        echo "--- filter config (skal gemmes som $TIMELAPSE_PRO_FILTER) ---"
        echo "$filter_content"
        echo "---"
    else
        log_info "Opretter filter config: $TIMELAPSE_PRO_FILTER"
        sudo mkdir -p "$(dirname "$TIMELAPSE_PRO_FILTER")"
        echo "$filter_content" | sudo tee "$TIMELAPSE_PRO_FILTER" >/dev/null
        log_ok "Filter config oprettet"
    fi

    # Reload fail2ban hvis ikke dry-run
    if [ "$dry_run" = false ]; then
        log_info "Reloader fail2ban..."
        sudo fail2ban-client reload 2>/dev/null || sudo brew services restart fail2ban
        log_ok "Fail2ban reloaded"
    fi

    log_section "Apply Resultat"
    if [ "$dry_run" = true ]; then
        log_ok "DRY-RUN gennemført — ingen ændringer udført"
    else
        log_ok "TimeLapse Pro fail2ban config installeret"
        log_info "Kør '$0' igen for verifikation"
    fi

    return 0
}

main() {
    local apply_mode=false
    local dry_run=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --apply)
                apply_mode=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Ukendt argument: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  TimeLapse Pro — Fail2ban Verifikation                          ║${NC}"
    echo -e "${BLUE}║  Version: 1.0.1 | Dato: 2026-07-07                               ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Apply mode?
    if [ "$apply_mode" = true ]; then
        apply_config "$([ "$dry_run" = true ] && echo "--dry-run" || echo "")"
        return $?
    fi

    # Verification mode (default)
    local errors=0

    check_fail2ban_installed || ((errors++))
    check_fail2ban_running || ((errors++))
    check_timelapse_jails || ((errors++))
    check_nginx_logs || ((errors++))
    show_active_bans
    show_fail2ban_log

    log_section "Resultat"
    if [ $errors -eq 0 ]; then
        log_ok "Alle tjek bestået! Fail2ban ser konfigureret korrekt."
        return 0
    else
        log_error "$errors tjek fejlede — se ovenstående detaljer."
        log_info "For at installere config, kør: $0 --apply"
        return 1
    fi
}

# Kør hovedprogram
main "$@"
