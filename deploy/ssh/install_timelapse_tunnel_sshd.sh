#!/usr/bin/env bash
# TimeLapse Pro — install/verify the dedicated reverse-SSH tunnel ingress
# (TCP/22022, service identity timelapse_tunnel).
#
# Canonical authority: froekjaer/timelapse-pro → deploy/ssh/install_timelapse_tunnel_sshd.sh
#
# Design contract: one dedicated sshd instance on 22022, public-key only,
# no PTY/shell/agent/X11, remote-forwarding only, loopback-bound forwards,
# and per-Edge authorized_keys entries of the form:
#   restrict,port-forwarding,permitlisten="127.0.0.1:<port>" <pubkey> <id>
#
# authorized_keys is deliberately root-owned but readable by the service
# identity. OpenSSH temporarily switches to the target user's uid before
# opening AuthorizedKeysFile, so a root-only 0600 file behind a 0700 root
# directory cannot authenticate this service account. The directory is 0711
# (traverse, no listing) and authorized_keys is 0644 (public key material;
# root-only write). sshd_config and the host private key remain 0600.
#
# The admin sshd (22/22222) and SFTP (22222) are never touched by this script.
#
# Usage:
#   sudo ./install_timelapse_tunnel_sshd.sh
#   sudo ./install_timelapse_tunnel_sshd.sh --verify-only
#   sudo ./install_timelapse_tunnel_sshd.sh --self-test
#   sudo ./install_timelapse_tunnel_sshd.sh --uninstall
set -euo pipefail

LABEL="dk.froekjaer.timelapse-tunnel-sshd"
CONF_DIR="/etc/ssh/timelapse-tunnel"
CONF_FILE="${CONF_DIR}/sshd_config"
AK_FILE="${CONF_DIR}/authorized_keys"
HOST_KEY="${CONF_DIR}/ssh_host_ed25519_key"
PLIST_DST="/Library/LaunchDaemons/${LABEL}.plist"
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$(cd "${SCRIPT_DIR}/.." && pwd)/launchd/${LABEL}.plist"
CONF_SRC="${SCRIPT_DIR}/timelapse-tunnel-sshd.conf"
AK_TEMPLATE="${SCRIPT_DIR}/authorized_keys.timelapse_tunnel"
USER_NAME="timelapse_tunnel"
TUNNEL_PORT=22022
SELFTEST_LISTEN=22998

log() { printf '[install-tunnel-sshd] %s\n' "$*"; }
die() { printf '[install-tunnel-sshd] FEJL: %s\n' "$*" >&2; exit 1; }
am_root() { [[ "$(id -u)" == 0 ]]; }

MODE="install"
case "${1:-}" in
    "") ;;
    --verify-only) MODE="verify" ;;
    --self-test) MODE="selftest" ;;
    --uninstall) MODE="uninstall" ;;
    *) die "unknown argument: ${1}" ;;
esac

report_runtime_state() {
    log "── RUNTIME STATE REPORT ──"
    if [[ -d "$CONF_DIR" ]]; then
        log "confdir:    PRESENT (${CONF_DIR}; $(stat -f '%Lp %Su:%Sg' "$CONF_DIR" 2>/dev/null || echo 'mode unknown'))"
    else
        log "confdir:    ABSENT"
    fi
    if [[ -f "$CONF_FILE" ]]; then log "config:     INSTALLED (${CONF_FILE})"; else log "config:     NOT INSTALLED"; fi
    if [[ -f "$AK_FILE" ]]; then
        log "authkeys:   PRESENT (${AK_FILE}; $(stat -f '%Lp %Su:%Sg' "$AK_FILE" 2>/dev/null || echo 'mode unknown'))"
    else
        log "authkeys:   ABSENT"
    fi
    if [[ -f "$HOST_KEY" ]]; then log "hostkey:    PRESENT"; else log "hostkey:    ABSENT"; fi
    if [[ -f "$PLIST_DST" ]]; then log "plist:      INSTALLED (${PLIST_DST})"; else log "plist:      NOT INSTALLED"; fi
    if launchctl print "system/${LABEL}" >/dev/null 2>&1; then log "launchd:    LOADED (system/${LABEL})"; else log "launchd:    NOT LOADED"; fi
    if lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
        log "listener:   ${TUNNEL_PORT} UP ($(lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN | tail -1 | awk '{print $1}'))"
    else
        log "listener:   ${TUNNEL_PORT} DOWN"
    fi
    if [[ -r "$HOST_KEY" ]]; then log "hostkey fp: $(ssh-keygen -lf "$HOST_KEY" | awk '{print $1, $2}')"; fi
}

# Read-only preflight shared by every mode.
[[ "$(uname -s)" == "Darwin" ]] || die "macOS-only script"
[[ -x /usr/sbin/sshd ]] || die "/usr/sbin/sshd missing"
[[ -f "$CONF_SRC" ]] || die "missing repo config: $CONF_SRC"
[[ -f "$PLIST_SRC" ]] || die "missing repo plist: $PLIST_SRC"
[[ -f "$AK_TEMPLATE" ]] || die "missing authorized_keys template: $AK_TEMPLATE"
log "OpenSSH: $(ssh -V 2>&1)"

# --verify-only is genuinely read-only: no mktemp, key generation, writes,
# permission changes, dscl mutation or launchctl mutation occur before exit.
if [[ "$MODE" == "verify" ]]; then
    if ! am_root; then
        log "verify-only (non-root): repo artefacts present; root runtime files not inspected."
        log "verify-only complete — NOTHING was modified."
        exit 0
    fi
    log "verify-only (root): read-only checks of installed/runtime state:"
    if [[ -f "$CONF_FILE" ]]; then
        if /usr/sbin/sshd -t -f "$CONF_FILE" 2>/dev/null; then
            log "installed config: sshd -t OK"
        else
            log "installed config: sshd -t FAILED"
        fi
    fi
    report_runtime_state
    log "verify-only complete — NOTHING was modified."
    exit 0
fi

am_root || die "install/self-test/uninstall require root. Re-run with sudo."

if [[ "$MODE" == "uninstall" ]]; then
    launchctl bootout "system/${LABEL}" 2>/dev/null && log "service booted out" || log "service not loaded"
    [[ -f "$PLIST_DST" ]] && rm -f "$PLIST_DST" && log "plist removed"
    if [[ -f "$AK_FILE" ]]; then
        BK="/var/backups/timelapse-tunnel-authorized_keys.$(date +%Y%m%d%H%M%S).bak"
        mkdir -p /var/backups
        cp "$AK_FILE" "$BK"
        chmod 600 "$BK"
        log "authorized_keys backed up to ${BK}"
    fi
    [[ -d "$CONF_DIR" ]] && rm -rf "$CONF_DIR" && log "config dir removed"
    log "uninstall complete. Account '${USER_NAME}' LEFT IN PLACE."
    report_runtime_state || true
    exit 0
fi

# Syntax-check the repo config only for modes that may activate it. This uses
# temporary material and therefore intentionally occurs after verify-only.
log "sshd config test (repo copy, temp hostkey):"
TMPDIR_CHK="$(mktemp -d)"
cleanup_preflight() { rm -rf "$TMPDIR_CHK"; }
trap cleanup_preflight EXIT
ssh-keygen -q -t ed25519 -N '' -f "${TMPDIR_CHK}/hk" -C tunnel-sshd-syntaxcheck >/dev/null
sed "s|^HostKey .*|HostKey ${TMPDIR_CHK}/hk|" "$CONF_SRC" > "${TMPDIR_CHK}/sshd_config"
/usr/sbin/sshd -t -f "${TMPDIR_CHK}/sshd_config" || die "repo sshd_config failed sshd -t"
cleanup_preflight
trap - EXIT
log "  syntax OK"

if lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN >/dev/null 2>&1 && \
   ! launchctl print "system/${LABEL}" >/dev/null 2>&1; then
    die "TCP/${TUNNEL_PORT} is already in use by something that is NOT ${LABEL}"
fi

# ═══════════════════ MUTATIONS BEGIN HERE (root only) ══════════════════════
if ! dscl . -read "/Users/${USER_NAME}" >/dev/null 2>&1; then
    log "creating service account ${USER_NAME} (no shell, no home)…"
    LAST_UID=$(dscl . -list /Users UniqueID | awk '{print $2}' | sort -n | tail -1)
    NEW_UID=$(( LAST_UID > 500 ? LAST_UID + 1 : 501 ))
    dscl . -create "/Users/${USER_NAME}" UniqueID "$NEW_UID"
    dscl . -create "/Users/${USER_NAME}" PrimaryGroupID 20
    dscl . -create "/Users/${USER_NAME}" UserShell /usr/bin/false
    dscl . -create "/Users/${USER_NAME}" RealName "TimeLapse Pro tunnel service"
    dscl . -create "/Users/${USER_NAME}" NFSHomeDirectory /var/empty
else
    log "service account ${USER_NAME} already exists — ensuring shell=false…"
    dscl . -create "/Users/${USER_NAME}" UserShell /usr/bin/false
fi

# Root keeps exclusive write control. 0711 lets the target uid traverse the
# known directory path; 0644 lets it read public authorized-key material.
mkdir -p "$CONF_DIR"
chown root:wheel "$CONF_DIR"
chmod 711 "$CONF_DIR"
install -m 600 -o root -g wheel "$CONF_SRC" "$CONF_FILE"

if [[ ! -f "$HOST_KEY" ]]; then
    log "generating dedicated ed25519 host key…"
    ssh-keygen -q -t ed25519 -N '' -f "$HOST_KEY" -C "${LABEL} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    chown root:wheel "$HOST_KEY"
    chmod 600 "$HOST_KEY"
else
    log "existing host key preserved (Edges may already pin it)."
fi

if [[ ! -f "$AK_FILE" ]]; then
    install -m 644 -o root -g wheel "$AK_TEMPLATE" "$AK_FILE"
    log "authorized_keys initialised from template (comment-only until Edge cutover)."
else
    log "existing authorized_keys CONTENT PRESERVED (device keys survive re-installs)."
fi
# Normalize permissions on both first install and repair/re-run.
chown root:wheel "$AK_FILE"
chmod 644 "$AK_FILE"
log "authorized_keys permissions: root:wheel 0644; config directory: root:wheel 0711"

/usr/sbin/sshd -t -f "$CONF_FILE" || { report_runtime_state; die "installed config failed sshd -t — aborting before activation"; }

install -m 644 -o root -g wheel "$PLIST_SRC" "$PLIST_DST"
plutil -lint "$PLIST_DST" >/dev/null || die "plist invalid"
launchctl bootout "system/${LABEL}" 2>/dev/null || true
launchctl bootstrap system "$PLIST_DST"
launchctl kickstart -k "system/${LABEL}"
sleep 2

post_fail() { report_runtime_state; die "$* (service may remain installed/running; remove with: sudo ${SCRIPT_PATH} --uninstall)"; }

lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN >/dev/null 2>&1 || post_fail "no listener on ${TUNNEL_PORT} after activation"
LISTEN_OWNER="$(lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN | tail -1 | awk '{print $1}')"
[[ "$LISTEN_OWNER" == sshd ]] || post_fail "listener on ${TUNNEL_PORT} is '${LISTEN_OWNER}', expected sshd"
log "listener ${TUNNEL_PORT}: dedicated sshd ✓"

for p in 8443 22222; do
    lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1 && log "regression: :$p still listening ✓" || post_fail ":$p stopped listening — REGRESSION"
done
for p in 2201 2204; do
    if lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; then
        log "regression: reverse :$p still listening (unchanged) ✓"
    else
        log "NOTE: reverse :$p not currently established (Edge offline?) — no change made by this script"
    fi
done

FP="$(ssh-keygen -lf "$HOST_KEY" | awk '{print $1, $2}')"
log "HOST KEY FINGERPRINT (${FP}) — record for Edge provisioning."

if [[ "$MODE" == "selftest" ]]; then
    ST="$(mktemp -d)"
    AK_RESTORED=0
    SELFTEST_SSH_PID=""

    cleanup_selftest() {
        if [[ -f "${ST}/ak.bak" && "$AK_RESTORED" -eq 0 ]]; then
            cp "${ST}/ak.bak" "$AK_FILE" 2>/dev/null || true
            chown root:wheel "$AK_FILE" 2>/dev/null || true
            chmod 644 "$AK_FILE" 2>/dev/null || true
            AK_RESTORED=1
        fi
        [[ -n "$SELFTEST_SSH_PID" ]] && kill "$SELFTEST_SSH_PID" 2>/dev/null || true
    }
    trap cleanup_selftest EXIT

    selftest_fail() {
        cleanup_selftest
        report_runtime_state
        log "SELVTEST FEJLEDE. Tjenesten på ${TUNNEL_PORT} forbliver INSTALLERET/KØRENDE medmindre rapporten ovenfor viser andet. Fjern helt med: sudo ${SCRIPT_PATH} --uninstall"
        die "$*"
    }

    log "── self-test with throwaway key (always removed afterwards) ──"
    ssh-keygen -q -t ed25519 -N '' -f "${ST}/k" -C selftest >/dev/null
    PUB="$(cat "${ST}/k.pub")"
    cp "$AK_FILE" "${ST}/ak.bak"
    printf 'restrict,port-forwarding,permitlisten="127.0.0.1:%s" %s selftest-%s\n' "$SELFTEST_LISTEN" "$PUB" "$(date +%s)" >> "$AK_FILE"

    SSHOPTS=(-i "${ST}/k" -p "$TUNNEL_PORT" -o BatchMode=yes -o StrictHostKeyChecking=no
             -o UserKnownHostsFile="${ST}/kh" -o ConnectTimeout=8 -o ExitOnForwardFailure=yes)

    ssh "${SSHOPTS[@]}" -N -R "127.0.0.1:${SELFTEST_LISTEN}:127.0.0.1:8000" "${USER_NAME}@127.0.0.1" &
    SELFTEST_SSH_PID=$!
    sleep 3
    lsof -nP -iTCP:"$SELFTEST_LISTEN" -sTCP:LISTEN 2>/dev/null | grep -q "127.0.0.1" \
        && log "selftest: reverse forward on 127.0.0.1:${SELFTEST_LISTEN} ✓" \
        || selftest_fail "selftest: allowed forward did not establish"

    if ssh "${SSHOPTS[@]}" "${USER_NAME}@127.0.0.1" echo hi 2>/dev/null | grep -q "hi"; then
        selftest_fail "selftest: command execution was NOT neutralised"
    fi
    log "selftest: command execution neutralised ✓"

    BADPORT=$((SELFTEST_LISTEN + 1))
    if (( BADPORT < 1 || BADPORT > 65535 || BADPORT == SELFTEST_LISTEN )); then
        selftest_fail "selftest: BADPORT=${BADPORT} is not a distinct valid TCP port"
    fi
    if lsof -nP -iTCP:"$BADPORT" -sTCP:LISTEN >/dev/null 2>&1; then
        selftest_fail "selftest: BADPORT ${BADPORT} already has a listener; cannot prove permitlisten refusal"
    fi

    set +e
    OUT_BAD="$(ssh "${SSHOPTS[@]}" -N \
        -R "127.0.0.1:${BADPORT}:127.0.0.1:8000" \
        "${USER_NAME}@127.0.0.1" 2>&1)"
    BAD_RC=$?
    set -e

    if (( BAD_RC == 0 )); then
        selftest_fail "selftest: non-allowed forward request on ${BADPORT} unexpectedly succeeded"
    fi
    if lsof -nP -iTCP:"$BADPORT" -sTCP:LISTEN >/dev/null 2>&1; then
        selftest_fail "selftest: non-allowed forward port (${BADPORT}) was PERMITTED — allowlist broken!"
    fi
    if [[ "$OUT_BAD" != *"remote port forwarding failed"* &&
          "$OUT_BAD" != *"administratively prohibited"* &&
          "$OUT_BAD" != *"cannot listen"* ]]; then
        selftest_fail "selftest: non-allowed forward failed without forwarding-refusal evidence: ${OUT_BAD}"
    fi
    log "selftest: valid non-allowed forward port ${BADPORT} refused by sshd policy ✓"

    OUT_PW="$(ssh -p "$TUNNEL_PORT" -o BatchMode=yes -o PubkeyAuthentication=no \
              -o PreferredAuthentications=password,keyboard-interactive \
              -o StrictHostKeyChecking=no -o UserKnownHostsFile="${ST}/kh" \
              "${USER_NAME}@127.0.0.1" true 2>&1 || true)"
    [[ "$OUT_PW" == *"Permission denied"* ]] && log "selftest: password auth denied ✓" \
        || selftest_fail "selftest: password path not denied: ${OUT_PW}"

    kill "$SELFTEST_SSH_PID" 2>/dev/null || true
    SELFTEST_SSH_PID=""
    cp "${ST}/ak.bak" "$AK_FILE"
    chown root:wheel "$AK_FILE"
    chmod 644 "$AK_FILE"
    AK_RESTORED=1
    sleep 1
    lsof -nP -iTCP:"$SELFTEST_LISTEN" -sTCP:LISTEN >/dev/null 2>&1 \
        && selftest_fail "selftest: allowed forward listener lingered after session termination" \
        || log "selftest: forward listener closed with session ✓"
    trap - EXIT
    rm -rf "$ST"
    log "selftest complete; throwaway key removed from authorized_keys."
fi

log "DONE. External NAT/firewall (TCP/${TUNNEL_PORT} → headend) is OUT of this script's scope."
log "Edge cutover is a separate phase — no Edge was touched."
