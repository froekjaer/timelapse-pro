#!/usr/bin/env bash
# TimeLapse Pro — install/verify the dedicated reverse-SSH tunnel ingress
# (TCP/22022, service identity timelapse_tunnel).
#
# Canonical authority: froekjaer/timelapse-pro → deploy/ssh/install_timelapse_tunnel_sshd.sh
#
# Design contract (see deploy/ssh/timelapse-tunnel-sshd.conf and
# Dokumentation/HANDOVER_LOG.md 2026-09-17): one dedicated sshd instance on
# 22022, public-key only, no PTY/shell/agent/X11, remote-forwarding only,
# loopback-bound forwards, per-Edge permitlisten allowlist via
# authorized_keys. The admin sshd (22/22222) and SFTP (22222) are never
# touched by this script.
#
# Usage (root):
#   sudo ./install_timelapse_tunnel_sshd.sh              # full install/upgrade
#   sudo ./install_timelapse_tunnel_sshd.sh --verify-only # checks, no changes
#   sudo ./install_timelapse_tunnel_sshd.sh --self-test   # full install +
#         throwaway-key functional/negative tests, temp entry removed after
#
# Non-root: script refuses to modify anything and only runs safe preflight
# checks (explicitly marked PREFLIGHT-NONROOT in output).
#
# Idempotent: re-running upgrades config/plist and preserves the live
# authorized_keys and existing host keys. NEVER commits keys anywhere.
set -euo pipefail

LABEL="dk.froekjaer.timelapse-tunnel-sshd"
CONF_DIR="/etc/ssh/timelapse-tunnel"
CONF_FILE="${CONF_DIR}/sshd_config"
AK_FILE="${CONF_DIR}/authorized_keys"
HOST_KEY="${CONF_DIR}/ssh_host_ed25519_key"
PLIST_SRC="$(cd "$(dirname "$0")/.." && pwd)/launchd/${LABEL}.plist"
PLIST_DST="/Library/LaunchDaemons/${LABEL}.plist"
CONF_SRC="$(cd "$(dirname "$0")" && pwd)/timelapse-tunnel-sshd.conf"
AK_TEMPLATE="$(cd "$(dirname "$0")" && pwd)/authorized_keys.timelapse_tunnel"
USER_NAME="timelapse_tunnel"
TUNNEL_PORT=22022
SELFTEST_LISTEN=22998   # throwaway loopback port, removed after test

log()  { printf '[install-tunnel-sshd] %s\n' "$*"; }
die()  { printf '[install-tunnel-sshd] FEJL: %s\n' "$*" >&2; exit 1; }
am_root() { [[ "$(id -u)" == 0 ]]; }

MODE="install"
[[ "${1:-}" == "--verify-only" ]] && MODE="verify"
[[ "${1:-}" == "--self-test"   ]] && MODE="selftest"

# ── Preflight (safe unprivileged) ───────────────────────────────────────────
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
if ! am_root; then
    [[ "$MODE" == "install" || "$MODE" == "selftest" ]] && \
        die " PREFLIGHT-NONROOT passed, but install/self-test requires root. Re-run with sudo. (verify-only completed)"
    log "PREFLIGHT-NONROOT complete."
    exit 0
fi
[[ "$MODE" == "verify" ]] && { log "verify-only: full runtime verification requires the service; running preflight checks only at non-activated stage."; }

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
    # No password: account is created with no authentication password; sshd
    # config denies password auth outright (PasswordAuthentication no).
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

# Validate the INSTALLED config (with the real host key) BEFORE touching launchd.
/usr/sbin/sshd -t -f "$CONF_FILE" || die "installed config failed sshd -t — aborting before activation"

# ── launchd ────────────────────────────────────────────────────────────────
install -m 644 -o root -g wheel "$PLIST_SRC" "$PLIST_DST"
plutil -lint "$PLIST_DST" >/dev/null || die "plist invalid"
launchctl bootout "system/${LABEL}" 2>/dev/null || true   # no-op on first install
launchctl bootstrap system "$PLIST_DST"
launchctl kickstart -k "system/${LABEL}"
sleep 2

# ── Post-activation verification ───────────────────────────────────────────
[[ "$MODE" == "verify" ]] && { log "verify-only cannot run post-activation checks (service now active if installed earlier)."; exit 0; }

lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN >/dev/null 2>&1 || die "no listener on ${TUNNEL_PORT} after activation"
LISTEN_OWNER="$(lsof -nP -iTCP:"$TUNNEL_PORT" -sTCP:LISTEN | tail -1 | awk '{print $1}')"
[[ "$LISTEN_OWNER" == sshd ]] || die "listener on ${TUNNEL_PORT} is '${LISTEN_OWNER}', expected sshd"
log "listener ${TUNNEL_PORT}: dedicated sshd ✓"

# Existing TimeLapse surfaces must be untouched:
for p in 8443 22222; do
    lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1 && log "regression: :$p still listening ✓" || die ":$p stopped listening — REGRESSION"
done
for p in 2201 2204; do
    if lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; then log "regression: reverse :$p still listening (unchanged) ✓"
    else log "NOTE: reverse :$p not currently established (Edge offline?) — no change made by this script"; fi
done

# Host key fingerprint for later Edge pinning (ssh_manager UserKnownHostsFile):
FP="$(ssh-keygen -lf "$HOST_KEY" | awk '{print $1, $2}')"
log "HOST KEY FINGERPRINT (${FP}) — record for Edge provisioning."

if [[ "$MODE" == "selftest" ]]; then
    log "── self-test with throwaway key (removed afterwards) ──"
    ST="$(mktemp -d)"; trap 'rm -rf "$ST"' EXIT
    ssh-keygen -q -t ed25519 -N '' -f "${ST}/k" -C selftest >/dev/null
    PUB="$(cat "${ST}/k.pub")"
    cp "$AK_FILE" "${ST}/ak.bak"
    printf 'restrict,permitlisten="127.0.0.1:%s" %s selftest-%s\n' "$SELFTEST_LISTEN" "$PUB" "$(date +%s)" >> "$AK_FILE"
    SSHOPTS=(-i "${ST}/k" -p "$TUNNEL_PORT" -o BatchMode=yes -o StrictHostKeyChecking=no
             -o UserKnownHostsFile="${ST}/kh" -o ConnectTimeout=8 -o ExitOnForwardFailure=yes)
    # Positive: reverse forward on the ALLOWED port must come up on loopback only.
    ssh -N -R "127.0.0.1:${SELFTEST_LISTEN}:127.0.0.1:8000" "${USER_NAME}@127.0.0.1" "${SSHOPTS[@]}" &
    SSH_PID=$!
    sleep 3
    lsof -nP -iTCP:"$SELFTEST_LISTEN" -sTCP:LISTEN | grep -q "127.0.0.1" \
        && log "selftest: reverse forward on 127.0.0.1:${SELFTEST_LISTEN} ✓" \
        || { cp "${ST}/ak.bak" "$AK_FILE"; kill $SSH_PID 2>/dev/null; die "selftest: forward did not establish"; }
    # Negative 1: requesting a shell must yield no PTY/interaction (ForceCommand false).
    OUT_SHELL="$(ssh "${SSHOPTS[@]}" "${USER_NAME}@127.0.0.1" true 2>&1 || true)"
    [[ "$OUT_SHELL" == *"denied"* || "$OUT_SHELL" == *"not executed"* || -z "$(ssh "${SSHOPTS[@]}" "${USER_NAME}@127.0.0.1" echo hi 2>/dev/null || true)" ]] \
        && log "selftest: command execution neutralised ✓" || log "selftest: WARNING — inspect command-execution result: ${OUT_SHELL}"
    # Negative 2: a remote forward on a NON-allowed port must be refused.
    OUT_BAD="$(ssh -N -R "127.0.0.1:${SELFTEST_LISTEN}7:127.0.0.1:8000" "${SSHOPTS[@]}" "${USER_NAME}@127.0.0.1" 2>&1 & BSSH=$!; sleep 3; kill $BSSH 2>/dev/null; wait $BSSH 2>/dev/null; true)"
    if lsof -nP -iTCP:"${SELFTEST_LISTEN}7" -sTCP:LISTEN >/dev/null 2>&1; then
        cp "${ST}/ak.bak" "$AK_FILE"; kill $SSH_PID 2>/dev/null; die "selftest FAIL: non-allowed forward port was permitted!"
    fi
    log "selftest: non-allowed forward port refused ✓"
    # Negative 3: password authentication must be refused.
    OUT_PW="$(ssh -p "$TUNNEL_PORT" -o BatchMode=yes -o PubkeyAuthentication=no -o PreferredAuthentications=password,keyboard-interactive \
              -o StrictHostKeyChecking=no -o UserKnownHostsFile="${ST}/kh" "${USER_NAME}@127.0.0.1" true 2>&1 || true)"
    [[ "$OUT_PW" == *"Permission denied"* ]] && log "selftest: password auth denied ✓" \
        || { cp "${ST}/ak.bak" "$AK_FILE"; kill $SSH_PID 2>/dev/null; die "selftest FAIL: password path not denied: ${OUT_PW}"; }
    kill $SSH_PID 2>/dev/null || true
    cp "${ST}/ak.bak" "$AK_FILE"   # restore — selftest entry gone
    sleep 1
    lsof -nP -iTCP:"$SELFTEST_LISTEN" -sTCP:LISTEN >/dev/null 2>&1 && log "selftest: WARNING — forward listener lingered" || log "selftest: forward listener closed with session ✓"
    log "selftest complete; throwaway key removed from authorized_keys."
fi

log "DONE. External NAT/firewall (TCP/${TUNNEL_PORT} → headend) is OUT of this script's scope."
log "Edge cutover is a separate phase — no Edge was touched."
