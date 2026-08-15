#!/usr/bin/env bash
# TimeLapse Pro — read-only Edge/Headend end-to-end diagnostics
#
# Security contract:
#   - no passwords or production URLs are embedded in the repository
#   - SSH host verification is mandatory
#   - SSH uses an explicitly supplied private-key path
#   - TLS certificate verification is mandatory
#   - this script NEVER deploys, pulls code, stashes changes or restarts services
#
# Example (run on the Headend, where the reverse tunnel and support key exist):
#   E2E_EDGE_PORT=2201 \
#   E2E_SSH_KEY="$HOME/.ssh/timelapse_headend_ed25519" \
#   E2E_HEADEND_URL="https://backend.example.invalid:8443/api" \
#   bash e2e_test.sh
set -euo pipefail

: "${E2E_EDGE_PORT:?Set E2E_EDGE_PORT to the active reverse-tunnel port}"
: "${E2E_SSH_KEY:?Set E2E_SSH_KEY to the authorised support private-key path}"
: "${E2E_HEADEND_URL:?Set E2E_HEADEND_URL to the HTTPS Headend API base URL}"

E2E_EDGE_HOST="${E2E_EDGE_HOST:-localhost}"
E2E_EDGE_USER="${E2E_EDGE_USER:-orangepi}"
E2E_KNOWN_HOSTS="${E2E_KNOWN_HOSTS:-$HOME/.ssh/known_hosts}"

[[ "$E2E_EDGE_PORT" =~ ^[0-9]+$ ]] || { echo "Invalid E2E_EDGE_PORT" >&2; exit 2; }
[[ -r "$E2E_SSH_KEY" ]] || { echo "SSH key not readable: $E2E_SSH_KEY" >&2; exit 2; }
[[ -r "$E2E_KNOWN_HOSTS" ]] || { echo "known_hosts not readable: $E2E_KNOWN_HOSTS" >&2; exit 2; }
[[ "$E2E_HEADEND_URL" == https://* ]] || { echo "E2E_HEADEND_URL must use https://" >&2; exit 2; }

SSH=(
  ssh
  -p "$E2E_EDGE_PORT"
  -i "$E2E_SSH_KEY"
  -o BatchMode=yes
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes
  -o "UserKnownHostsFile=$E2E_KNOWN_HOSTS"
  "$E2E_EDGE_USER@$E2E_EDGE_HOST"
)

ok()  { echo "  ✓ $*"; }
err() { echo "  ✗ $*" >&2; }
sep() { echo; echo "══ $* ══════════════════════════════════════════"; }

remote() {
  "${SSH[@]}" "$@"
}

sep "1. Verified SSH tunnel"
if remote "printf '%s\\n' ok" >/dev/null; then
  ok "SSH connected with strict host-key verification"
else
  err "Cannot connect through verified tunnel on $E2E_EDGE_HOST:$E2E_EDGE_PORT"
  exit 1
fi

sep "2. Runtime identity (read-only)"
DEVICE_ID="$(remote "sed -n 's/^[[:space:]]*device_id:[[:space:]]*[\"'\"']*\\([^\"'\"']*\\)[\"'\"']*.*/\\1/p' /etc/timelapse/bootstrap.yaml 2>/dev/null | head -1" || true)"
APP_VERSION="$(remote "python3 - <<'PY'
from pathlib import Path
for path in (Path('/opt/timelapse/VERSION'), Path('/etc/timelapse/release-version')):
    if path.is_file():
        print(path.read_text().strip())
        break
PY" || true)"
[[ -n "$DEVICE_ID" ]] || DEVICE_ID="unknown"
echo "  Device ID: $DEVICE_ID"
echo "  App/release: ${APP_VERSION:-unknown}"

sep "3. Services and storage (read-only)"
remote "systemctl is-active timelapse-edge 2>/dev/null || true; df -h / /data 2>/dev/null || df -h /" | sed 's/^/  /'

sep "4. Camera/USB evidence (read-only)"
remote "printf '%s\\n' 'USB:'; lsusb 2>/dev/null || true; printf '%s\\n' 'PTP:'; gphoto2 --auto-detect 2>/dev/null || true" | sed 's/^/  /'

sep "5. Recent Edge logs (read-only)"
remote "journalctl -u timelapse-edge -n 40 --no-pager 2>/dev/null || true" \
  | grep -E "camera|Camera|PTP|capture|upload|heartbeat|ERROR|WARNING" \
  | tail -30 \
  | sed 's/^/  /' || true

sep "6. Headend TLS/API reachability"
# No -k/--insecure: a certificate failure is a test failure.
HEALTH_URL="${E2E_HEADEND_URL%/api}/api/health"
if curl --fail --silent --show-error --max-time 15 "$HEALTH_URL" >/dev/null; then
  ok "Headend HTTPS certificate and health endpoint verified"
else
  err "Headend HTTPS/API health verification failed"
  exit 1
fi

sep "Færdig"
echo "  Read-only E2E diagnostics passed for $DEVICE_ID"
echo "  No code, credentials, services, GPIO or capture data were changed."
