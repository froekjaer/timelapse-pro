#!/usr/bin/env bash
# Install the dedicated remote ADMIN sshd for the Headend (TCP/9122):
# macOS password + TOTP via PAM keyboard-interactive; only forward = 5900.
#
#   sudo deploy/ssh/install_timelapse_admin_sshd.sh                # install/repair
#   sudo deploy/ssh/install_timelapse_admin_sshd.sh --verify-only  # read-only checks
#   sudo deploy/ssh/install_timelapse_admin_sshd.sh --uninstall
#
# Prerequisite (separate, deliberate steps — see
# Dokumentation/ADMIN_REMOTE_ACCESS_9122_2026-10-01.md): root-owned
# pam_google_authenticator in /usr/local/lib/pam, its line in /etc/pam.d/sshd,
# and the admin user's ~/.google_authenticator. The installer REFUSES to start
# the service if any of these is missing, because without them 9122 would be
# password-only.
#
# Env: TL_ADMIN_USER (default: peter).
# Modelled on the tunnel ingress installer (#259 install_timelapse_tunnel_sshd.sh).
# Does NOT modify /etc/ssh/sshd_config, /etc/pam.d/sshd, port 22 or the SFTP socket.
# External NAT/firewall (TCP/9122 -> Headend) is out of scope.
set -euo pipefail

LABEL="dk.froekjaer.timelapse-admin-sshd"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONF_SRC="${SCRIPT_DIR}/timelapse-admin-sshd.conf"
PLIST_SRC="${REPO_ROOT}/deploy/launchd/${LABEL}.plist"
CONF_DIR="/etc/ssh/timelapse-admin"
CONF_FILE="${CONF_DIR}/sshd_config"
HOST_KEY="${CONF_DIR}/ssh_host_ed25519_key"
PAM_MODULE="/usr/local/lib/pam/pam_google_authenticator.so"
PAM_FILE="/etc/pam.d/sshd"
PLIST_DST="/Library/LaunchDaemons/${LABEL}.plist"
ADMIN_USER="${TL_ADMIN_USER:-peter}"

log() { printf '[install-admin-sshd] %s\n' "$*"; }
die() { printf '[install-admin-sshd] FEJL: %s\n' "$*" >&2; exit 1; }

MODE="install"
case "${1:-}" in
    "") ;;
    --verify-only) MODE="verify" ;;
    --uninstall) MODE="uninstall" ;;
    *) die "ukendt argument: ${1}" ;;
esac
[[ "$(id -u)" == 0 ]] || die "kør med sudo"

ADMIN_PORT="$(awk '$1=="Port"{print $2; exit}' "$CONF_SRC")"
[[ "$ADMIN_PORT" =~ ^[0-9]+$ ]] && (( ADMIN_PORT < 10000 )) || die "admin-port skal være under 10000 (PORTS.md)"
[[ "$ADMIN_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die "ugyldigt TL_ADMIN_USER"
id "$ADMIN_USER" >/dev/null 2>&1 || die "brugeren ${ADMIN_USER} findes ikke"

service_pid() { { launchctl print "system/${LABEL}" 2>/dev/null || true; } | awk '$1=="pid"{print $3; exit}'; }
port_pids() { { lsof -nP -t -iTCP:"$1" -sTCP:LISTEN 2>/dev/null || true; } | sort -u | paste -sd, -; }

admin_home() { dscl . -read "/Users/${ADMIN_USER}" NFSHomeDirectory | awk '{print $2}'; }

check_totp_prereqs() {
    local ok=0 home
    home="$(admin_home)"
    local mode
    mode="$(stat -f '%Lp' "$PAM_MODULE" 2>/dev/null || echo 777)"
    if [[ -f "$PAM_MODULE" && "$(stat -f '%Su' "$PAM_MODULE")" == root && $(( 8#$mode & 8#022 )) -eq 0 ]]; then
        log "PAM-modul: ${PAM_MODULE} (root, ${mode})"
    else
        log "PAM-modul: MANGLER, ikke root-ejet eller skrivbart for andre (${PAM_MODULE})"; ok=1
    fi
    if grep -Eq "^auth[[:space:]]+required[[:space:]]+${PAM_MODULE}( |$)" "$PAM_FILE"; then
        log "PAM: ${PAM_FILE} kræver TOTP-modulet"
    else
        log "PAM: ${PAM_FILE} indeholder IKKE TOTP-linjen"; ok=1
    fi
    if [[ -s "${home}/.google_authenticator" ]]; then
        log "TOTP-nøgle: ${home}/.google_authenticator ($(stat -f '%Lp %Su' "${home}/.google_authenticator"))"
    else
        log "TOTP-nøgle: MANGLER for ${ADMIN_USER} — 9122 ville være password-only"; ok=1
    fi
    return $ok
}

verify() {
    local pid pids rc=0
    pid="$(service_pid)"; pids="$(port_pids "$ADMIN_PORT")"
    [[ -n "$pid" ]] && log "launchd: ${LABEL} kører (pid ${pid})" || { log "launchd: ${LABEL} kører IKKE"; rc=1; }
    if [[ -n "$pids" && "$pids" == "$pid" ]]; then log "lytter: TCP/${ADMIN_PORT} ejet af pid ${pid} ✓"; else log "lytter: TCP/${ADMIN_PORT} pid='${pids}' (forventet ${pid:-?})"; rc=1; fi
    check_totp_prereqs || rc=1
    /usr/sbin/sshd -t -f "$CONF_FILE" 2>/dev/null && log "sshd -t: OK" || { log "sshd -t: FEJL"; rc=1; }
    return $rc
}

case "$MODE" in
    verify) verify; exit $? ;;
    uninstall)
        launchctl bootout "system/${LABEL}" 2>/dev/null || true
        rm -f "$PLIST_DST"; rm -rf "$CONF_DIR"
        log "afinstalleret (PAM-linje, PAM-modul og ~/.google_authenticator er IKKE rørt)"
        exit 0 ;;
esac

# ── Preflight (no mutations) ─────────────────────────────────────────────────
check_totp_prereqs || die "TOTP-forudsætninger mangler — 9122 startes ikke som password-only (se dokumentationen)"
for f in "$CONF_SRC" "$PLIST_SRC"; do
    [[ -f "$f" ]] || die "mangler ${f}"
done
dseditgroup -o checkmember -m "$ADMIN_USER" com.apple.access_ssh >/dev/null 2>&1 \
    || log "ADVARSEL: ${ADMIN_USER} er ikke i com.apple.access_ssh (macOS 'Fjernlogin') — password-login vil blive afvist af PAM"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
ssh-keygen -q -t ed25519 -N '' -f "${TMP}/hk" >/dev/null
sed -e "s|^HostKey .*|HostKey ${TMP}/hk|" -e "s|__ADMIN_USER__|${ADMIN_USER}|" "$CONF_SRC" > "${TMP}/sshd_config"
/usr/sbin/sshd -t -f "${TMP}/sshd_config" || die "repo-konfigurationen fejlede sshd -t"
SERVICE_PID="$(service_pid)"; PIDS="$(port_pids "$ADMIN_PORT")"
if [[ -n "$PIDS" && "$PIDS" != "$SERVICE_PID" ]]; then
    die "TCP/${ADMIN_PORT} bruges af pid ${PIDS}, som ikke er ${LABEL}"
fi

# ── Install ──────────────────────────────────────────────────────────────────
install -d -m 755 -o root -g wheel "$CONF_DIR"
sed -e "s|__ADMIN_USER__|${ADMIN_USER}|" "$CONF_SRC" > "${TMP}/rendered"
install -m 600 -o root -g wheel "${TMP}/rendered" "$CONF_FILE"
if [[ ! -f "$HOST_KEY" ]]; then
    ssh-keygen -q -t ed25519 -N '' -f "$HOST_KEY" -C "${LABEL}"
    chmod 600 "$HOST_KEY"
    log "ny host-nøgle: $(ssh-keygen -lf "${HOST_KEY}.pub")"
else
    log "eksisterende host-nøgle bevaret: $(ssh-keygen -lf "${HOST_KEY}.pub")"
fi
/usr/sbin/sshd -t -f "$CONF_FILE" || die "installeret konfiguration fejlede sshd -t"
install -m 644 -o root -g wheel "$PLIST_SRC" "$PLIST_DST"
plutil -lint "$PLIST_DST" >/dev/null || die "plist ugyldig"
if [[ -n "$SERVICE_PID" ]]; then
    # Reload config without dropping existing admin sessions.
    kill -HUP "$SERVICE_PID"
    log "eksisterende ${LABEL} genindlæst (HUP) — aktive sessioner bevaret"
else
    launchctl bootstrap system "$PLIST_DST"
fi
sleep 2
verify || die "verifikation fejlede — se ovenfor (fjern med: sudo $0 --uninstall)"
log "FÆRDIG. Test lokalt: ssh -p ${ADMIN_PORT} ${ADMIN_USER}@127.0.0.1  (adgangskode + TOTP-kode)"
log "Router: viderestil TCP/${ADMIN_PORT} -> denne Headend (ligger uden for dette script)."
