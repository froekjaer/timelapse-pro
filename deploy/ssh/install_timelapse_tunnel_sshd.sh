#!/usr/bin/env bash
# TimeLapse Pro — install/verify the dedicated reverse-SSH tunnel ingress
# (TCP/22022, service identity timelapse_tunnel).
#
# Canonical authority: froekjaer/timelapse-pro → deploy/ssh/install_timelapse_tunnel_sshd.sh
#
# Design contract (see deploy/ssh/timelapse-tunnel-sshd.conf and
# Dokumentation/HANDOVER_LOG.md 2026-09-17): one dedicated sshd instance on
# 22022, public-key only, no PTY/shell/agent/X11, remote-forwarding only,
# loopback-bound forwards, per-Edge allowlist via authorized_keys entries of
# the form:
#     restrict,port-forwarding,permitlisten="127.0.0.1:<port>" <pubkey> <id>
# (`restrict` disables ALL forwarding; `port-forwarding` re-enables it;
#  `permitlisten` then narrows it to exactly one loopback listen port.
#  `permitlisten` ALONE re-enables nothing — see AUTHORIZED_KEYS in sshd(8)
#  and the regression tests in tests/test_timelapse_tunnel_sshd_config.py.)
#
# The admin sshd (22/22222) and SFTP (22222) are never touched by this script.
#
# Usage:
#   sudo ./install_timelapse_tunnel_sshd.sh                 # full install/upgrade
#   sudo ./install_timelapse_tunnel_sshd.sh --verify-only    # PROVABLY read-only:
#        checks + reports installed/runtime state, performs ZERO mutations
#        (no dscl writes, no mkdir/install/chown/chmod, no key generation,
#         no launchctl bootout/bootstrap/kickstart).
#   sudo ./install_timelapse_tunnel_sshd.sh --self-test      # full install +
#        throwaway-key functional/negative tests (temp entry always removed)
#   sudo ./install_timelapse_tunnel_sshd.sh --uninstall      # removes service,
#        plist and /etc/ssh/timelapse-tunnel; backs up authorized_keys to
#        /var/backups; never touches anything else.
#
# Non-root: refuses to modify anything; runs safe preflight only.
# Idempotent: re-running upgrades config/plist and preserves live
# authorized_keys and existing host keys. NEVER commits keys anywhere.
#
# SELF-TEST FAILURE SEMANTICS (deliberate, deterministic):
#   The service is activated BEFORE the self-test runs. If any self-test
#   fails, the throwaway key is always removed (EXIT trap), and the script
#   prints an explicit RUNTIME STATE REPORT stating whether the 22022 service
#   is still installed and running, plus the exact removal command
#   (--uninstall). No failure leaves state ambiguous. Rollback is NOT
#   automatic on purpose: an activated-but-failing listener is safer to
#   diagnose in place than to tear down blindly.
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
SELFTEST_LISTEN=22998   # throwaway loopback port, removed after test

log() { printf '[install-tunnel-sshd] %s\n' "$*"; }
die() { printf '[install-tunnel-sshd] FEJL: %s\n' "$*" >&2; exit 1; }
am_root() { [[ "$(id -u)" == 0 ]]; }

MODE="install"
case "${1:-}" in
    --verify-only) MODE="verify" ;;
    --self-test)   MODE="selftest" ;;
    --uninstall)   MODE="uninstall" ;;
esac

# Deterministic runtime-state report (used on failures AND by --verify-only).
report_runtime_state() {
    log "── RUNTIME STATE REPORT ──"
    if [[ -f "$CONF_FILE" ]]; then log "config:     INSTALLED (${CONF_FILE})"; else log "config:     NOT INSTALLED"; fi
    if [[ -f "$AK_FILE" ]];    then log "authkeys:   PRESENT (${AK_FILE})";   else log "authkeys:   ABSENT"; fi
    if [[ -f "$HOST_KEY" ]];   then log "hostkey:    PRESENT";                else log "hostkey:    ABSENT"; fi
    if [[ -f "$PLIST_DST" ]];  then log "plist:      INSTALLED (${PLIST_DST})"; else log "plist:      NOT INSTALLED"; fi
    if launchctl print "system/${LABEL}" >/dev/null 2>&1; then log "launchd:    LOADED (system/${LABEL})"; else log "launchd:    NOT LOADED"; fi
    if lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
        log "listener:   ${TUNNEL_PORT} UP ($(lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN | tail -1 | awk '{print $1}'))"
    else
        log "listener:   ${TUNNEL_PORT} DOWN"
    fi
    if [[ -f "$HOST_KEY" ]]; then log "hostkey fp: $(ssh-keygen -lf "$HOST_KEY" | awk '{print $1, $2}')"; fi
}

# ── Preflight (safe, no mutations) ─────────────────────────────────────────
[[ "$(uname -s)" == "Darwin" ]] || die "macOS-only script"
[[ -x /usr/sbin/sshd ]] || die "/usr/sbin/sshd missing"
[[ -f "$CONF_SRC" ]]   || die "missing repo config: $CONF_SRC"
[[ -f "$PLIST_SRC" ]]  || die "missing repo plist: $PLIST_SRC"
log "OpenSSH: $(ssh -V 2>&1)"
log "sshd config test (repo copy, temp hostkey):"
TMPDIR_CHK="$(mktemp -d)"
ssh-keygen -q -t ed25519 -N '' -f "${TMPDIR_CHK}/hk" -C tunnel-sshd-syntaxcheck >/dev/null
sed "s|^HostKey .*|HostKey ${TMPDIR_CHK}/hk|" "$CONF_SRC" > "${TMPDIR_CHK}/sshd_config"
/usr/sbin/sshd -t -f "${TMPDIR_CHK}/sshd_config" && log "  syntax OK" || die "repo sshd_config failed sshd -t"
rm -rf "$TMPDIR_CHK"

if lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN >/dev/null 2>&1 && \
   ! launchctl print "system/${LABEL}" >/dev/null 2>&1; then
    die "TCP/${TUNNEL_PORT} is already in use by something that is NOT ${LABEL} — resolve manually first"
fi

# ── --verify-only: PROVABLY READ-ONLY PATH — exits BEFORE any mutation ─────
# Guarded mode check placed BEFORE the non-root guard so that the read-only
# contract holds for BOTH root and non-root callers: from here on in this
# branch there is no dscl write, no mkdir/install/chown/chmod, no key
# generation, and no launchctl mutation — only existence checks, sshd -t
# against already-installed files, and reporting.
if [[ "$MODE" == "verify" ]]; then
    if ! am_root; then
        log "verify-only (non-root): structural checks above ran read-only."
        log "verify-only (non-root) complete — no mutations performed."
        exit 0
    fi
    log "verify-only (root): read-only checks of any INSTALLED state:"
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

# ── --uninstall ─────────────────────────────────────────────────────────────
if [[ "$MODE" == "uninstall" ]]; then
    launchctl bootout "system/${LABEL}" 2>/dev/null && log "service booted out" || log "service not loaded"
    [[ -f "$PLIST_DST" ]] && rm -f "$PLIST_DST" && log "plist removed"
    if [[ -f "$AK_FILE" ]]; then
        BK="/var/backups/timelapse-tunnel-authorized_keys.$(date +%Y%m%d%H%M%S).bak"
        mkdir -p /var/backups; cp "$AK_FILE" "$BK"; chmod 600 "$BK"
        log "authorized_keys backed up to ${BK}"
    fi
    [[ -d "$CONF_DIR" ]] && rm -rf "$CONF_DIR" && log "config dir removed"
    log "uninstall complete. Account '${USER_NAME}' LEFT IN PLACE (harmless without service; delete manually if desired)."
    report_runtime_state || true
    exit 0
fi

# ═══════════════════ MUTATIONS BEGIN HERE (root only) ══════════════════════
# verify-only has exited above; --self-test and install continue past here.

# ── Service identity ───────────────────────────────────────────────────────
if ! dscl . -read "/Users/${USER_NAME}" >/dev/null 2>&1; then
    log "creating service account ${USER_NAME} (no shell, no home)…"
    LAST_UID=$(dscl . -list /Users UniqueID | awk '{print $2}' | sort -n | tail -1)
    NEW_UID=$(( LAST_UID > 500 ? LAST_UID + 1 : 501 ))
    dscl . -create "/Users/${USER_NAME}" UniqueID "$NEW_UID"
    dscl . -create "/Users/${USER_NAME}" PrimaryGroupID 20   # staff (matches 'tunnel' precedent)
    dscl . -create "/Users/${USER_NAME}" UserShell /usr/bin/false
    dscl . -create "/Users/${USER_NAME}" RealName "TimeLapse Pro tunnel service"
    dscl . -create "/Users/${USER_NAME}" NFSHomeDirectory /var/empty
    # No password is ever set; sshd_config denies password auth outright.
else
    log "service account ${USER_NAME} already exists — ensuring shell=false…"
    dscl . -create "/Users/${USER_NAME}" UserShell /usr/bin/false
fi

# ── Config, host key, authorized_keys ──────────────────────────────────────
mkdir -p "$CONF_DIR"; chmod 700 "$CONF_DIR"; chown root:wheel "$CONF_DIR"
install -m 600 -o root -g wheel "$CONF_SRC" "$CONF_FILE"

if [[ ! -f "$HOST_KEY" ]]; then
    log "generating dedicated ed25519 host key…"
    ssh-keygen -q -t ed25519 -N '' -f "$HOST_KEY" -C "${LABEL} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    chown root:wheel "$HOST_KEY"; chmod 600 "$HOST_KEY"
else
    log "existing host key preserved (Edges may already pin it)."
fi

if [[ ! -f "$AK_FILE" ]]; then
    install -m 600 -o root -g wheel "$AK_TEMPLATE" "$AK_FILE"
    log "authorized_keys initialised from template (comment-only until Edge cutover)."
else
    log "existing authorized_keys PRESERVED (device keys survive re-installs)."
fi

# Validate the INSTALLED config BEFORE touching launchd.
/usr/sbin/sshd -t -f "$CONF_FILE" || { report_runtime_state; die "installed config failed sshd -t — aborting before activation"; }

# ── launchd ────────────────────────────────────────────────────────────────
install -m 644 -o root -g wheel "$PLIST_SRC" "$PLIST_DST"
plutil -lint "$PLIST_DST" >/dev/null || die "plist invalid"
launchctl bootout "system/${LABEL}" 2>/dev/null || true   # no-op on first install
launchctl bootstrap system "$PLIST_DST"
launchctl kickstart -k "system/${LABEL}"
sleep 2

# ── Post-activation verification ───────────────────────────────────────────
post_fail() { report_runtime_state; die "$* (see RUNTIME STATE REPORT above — service may be installed/running; remove with: sudo ${SCRIPT_PATH} --uninstall)"; }

lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN >/dev/null 2>&1 || post_fail "no listener on ${TUNNEL_PORT} after activation"
LISTEN_OWNER="$(lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN | tail -1 | awk '{print $1}')"
[[ "$LISTEN_OWNER" == sshd ]] || post_fail "listener on ${TUNNEL_PORT} is '${LISTEN_OWNER}', expected sshd"
log "listener ${TUNNEL_PORT}: dedicated sshd ✓"

for p in 8443 22222; do
    lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1 && log "regression: :$p still listening ✓" || post_fail ":$p stopped listening — REGRESSION"
done
for p in 2201 2204; do
    if lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; then log "regression: reverse :$p still listening (unchanged) ✓"
    else log "NOTE: reverse :$p not currently established (Edge offline?) — no change made by this script"; fi
done

FP="$(ssh-keygen -lf "$HOST_KEY" | awk '{print $1, $2}')"
log "HOST KEY FINGERPRINT (${FP}) — record for Edge provisioning."

# ── --self-test (service is NOW active; failures report state deterministically) ──
if [[ "$MODE" == "selftest" ]]; then
    ST="$(mktemp -d)"
    AK_RESTORED=0
    SELFTEST_SSH_PID=""
    cleanup_selftest() {
        if [[ -f "${ST}/ak.bak" && "$AK_RESTORED" -eq 0 ]]; then
            cp "${ST}/ak.bak" "$AK_FILE" 2>/dev/null && AK_RESTORED=1
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
    # Entry syntax: restrict → disables all forwarding;
    #               port-forwarding → re-enables forwarding;
    #               permitlisten → narrows remote listen to ONE loopback port.
    printf 'restrict,port-forwarding,permitlisten="127.0.0.1:%s" %s selftest-%s\n' "$SELFTEST_LISTEN" "$PUB" "$(date +%s)" >> "$AK_FILE"

    # ALL ssh options must appear BEFORE the destination host — anything after
    # the destination is parsed as a remote command (regression-tested).
    SSHOPTS=(-i "${ST}/k" -p "$TUNNEL_PORT" -o BatchMode=yes -o StrictHostKeyChecking=no
             -o UserKnownHostsFile="${ST}/kh" -o ConnectTimeout=8 -o ExitOnForwardFailure=yes)

    # Positive: reverse forward on the ALLOWED port must come up on loopback only.
    ssh "${SSHOPTS[@]}" -N -R "127.0.0.1:${SELFTEST_LISTEN}:127.0.0.1:8000" "${USER_NAME}@127.0.0.1" &
    SELFTEST_SSH_PID=$!
    sleep 3
    lsof -nP -iTCP:"$SELFTEST_LISTEN" -sTCP:LISTEN 2>/dev/null | grep -q "127.0.0.1" \
        && log "selftest: reverse forward on 127.0.0.1:${SELFTEST_LISTEN} ✓" \
        || selftest_fail "selftest: allowed forward did not establish"

    # Negative 1: command execution must be neutralised (ForceCommand /usr/bin/false).
    if ssh "${SSHOPTS[@]}" "${USER_NAME}@127.0.0.1" echo hi 2>/dev/null | grep -q "hi"; then
        selftest_fail "selftest: command execution was NOT neutralised"
    fi
    log "selftest: command execution neutralised ✓"

    # Negative 2: use a VALID but NON-allowed remote port so the refusal proves
    # the server-side permitlisten policy, not merely client-side port parsing.
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

    # Negative 3: password authentication must be refused.
    OUT_PW="$(ssh -p "$TUNNEL_PORT" -o BatchMode=yes -o PubkeyAuthentication=no \
              -o PreferredAuthentications=password,keyboard-interactive \
              -o StrictHostKeyChecking=no -o UserKnownHostsFile="${ST}/kh" \
              "${USER_NAME}@127.0.0.1" true 2>&1 || true)"
    [[ "$OUT_PW" == *"Permission denied"* ]] && log "selftest: password auth denied ✓" \
        || selftest_fail "selftest: password path not denied: ${OUT_PW}"

    kill "$SELFTEST_SSH_PID" 2>/dev/null || true
    cp "${ST}/ak.bak" "$AK_FILE"; AK_RESTORED=1
    sleep 1
    lsof -nP -iTCP:"$SELFTEST_LISTEN" -sTCP:LISTEN >/dev/null 2>&1 \
        && log "selftest: WARNING — forward listener lingered" \
        || log "selftest: forward listener closed with session ✓"
    trap - EXIT
    rm -rf "$ST"
    log "selftest complete; throwaway key removed from authorized_keys."
fi

log "DONE. External NAT/firewall (TCP/${TUNNEL_PORT} → headend) is OUT of this script's scope."
log "Edge cutover is a separate phase — no Edge was touched."
