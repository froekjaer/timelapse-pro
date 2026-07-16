#!/bin/zsh
# Enroll a macOS Headend using a short-lived bootstrap token, then install and
# verify the node agent. Secrets are read from files and never passed as args.
set -euo pipefail

log() { printf '[headend-enroll] %s\n' "$*"; }
die() { printf '[headend-enroll] ERROR: %s\n' "$*" >&2; exit 1; }

DEVICE_ID=""
HEADEND_URL=""
BOOTSTRAP_TOKEN_FILE=""
REPO_DIR=""
REPLACE_CONFIG=0

while (( $# )); do
  case "$1" in
    --device-id) DEVICE_ID="$2"; shift 2 ;;
    --headend-url) HEADEND_URL="${2%/}"; shift 2 ;;
    --bootstrap-token-file) BOOTSTRAP_TOKEN_FILE="$2"; shift 2 ;;
    --repo-dir) REPO_DIR="$2"; shift 2 ;;
    --replace-config) REPLACE_CONFIG=1; shift ;;
    -h|--help)
      cat <<'EOF'
Usage: sudo enroll_headend_cmdb.sh --device-id TL-HEADEND-STAGING-1 \
  --headend-url https://staging.timelapse-pro.dk:8443 \
  --bootstrap-token-file /secure/bootstrap-token --repo-dir /path/to/signed/release
EOF
      exit 0 ;;
    *) die "Ukendt argument: $1" ;;
  esac
done

[[ "$(id -u)" == 0 ]] || die "Kør med sudo"
[[ "$DEVICE_ID" == TL-* ]] || die "--device-id skal starte med TL-"
[[ "$HEADEND_URL" == https://* ]] || die "--headend-url skal bruge https"
[[ -r "$BOOTSTRAP_TOKEN_FILE" ]] || die "Bootstrap-tokenfilen kan ikke læses"
[[ -d "$REPO_DIR/node-agent" ]] || die "--repo-dir peger ikke på en TimeLapse release"

WORK_DIR="$(mktemp -d /tmp/timelapse-headend-enroll.XXXXXX)"
TOKEN_FILE="$WORK_DIR/api-token"
RESPONSE_FILE="$WORK_DIR/enrollment.json"
chmod 700 "$WORK_DIR"
trap 'rm -rf "$WORK_DIR"' EXIT

export TL_ENROLL_DEVICE_ID="$DEVICE_ID"
export TL_ENROLL_HEADEND_URL="$HEADEND_URL"
export TL_ENROLL_BOOTSTRAP_TOKEN_FILE="$BOOTSTRAP_TOKEN_FILE"
export TL_ENROLL_RESPONSE_FILE="$RESPONSE_FILE"
export TL_ENROLL_API_TOKEN_FILE="$TOKEN_FILE"

log "Enroll'er $DEVICE_ID som headend"
python3 <<'PY'
import json, os, pathlib, urllib.request

token = pathlib.Path(os.environ["TL_ENROLL_BOOTSTRAP_TOKEN_FILE"]).read_text().strip()
if not token:
    raise SystemExit("Bootstrap-tokenfilen er tom")
payload = json.dumps({
    "bootstrap_token": token,
    "device_id": os.environ["TL_ENROLL_DEVICE_ID"],
    "node_type": "headend",
    "hardware_model": "macos-headend",
}).encode()
request = urllib.request.Request(
    os.environ["TL_ENROLL_HEADEND_URL"] + "/api/devices/enroll",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    result = json.loads(response.read())
if result.get("device_id") != os.environ["TL_ENROLL_DEVICE_ID"] or not result.get("api_token"):
    raise SystemExit("Headend returnerede et ugyldigt enrollment-svar")
pathlib.Path(os.environ["TL_ENROLL_RESPONSE_FILE"]).write_text(
    json.dumps({k: v for k, v in result.items() if k != "api_token"}, indent=2) + "\n"
)
token_path = pathlib.Path(os.environ["TL_ENROLL_API_TOKEN_FILE"])
token_path.write_text(result["api_token"] + "\n")
token_path.chmod(0o600)
PY

LOG_FILE="/var/log/timelapse-node-agent.log"
LOG_START_LINE=1
if [[ -f "$LOG_FILE" ]]; then
  LOG_START_LINE=$(( $(wc -l < "$LOG_FILE") + 1 ))
fi

INSTALL_ARGS=(
  --device-id "$DEVICE_ID"
  --headend-url "$HEADEND_URL"
  --api-token-file "$TOKEN_FILE"
)
(( REPLACE_CONFIG )) && INSTALL_ARGS+=(--replace-config)
bash "$REPO_DIR/node-agent/install/macos.sh" "${INSTALL_ARGS[@]}"

log "Venter på autentificeret inventory-kvittering"
for attempt in {1..30}; do
  if tail -n "+$LOG_START_LINE" "$LOG_FILE" 2>/dev/null | grep -q "Inventar rapporteret OK"; then
    log "Enrollment verificeret: node-agent har rapporteret inventory til CMDB"
    cat "$RESPONSE_FILE"
    exit 0
  fi
  sleep 2
done
die "Ingen ny inventory-kvittering inden 60 sekunder; se $LOG_FILE"
