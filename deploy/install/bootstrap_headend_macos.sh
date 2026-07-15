#!/bin/zsh
# Controlled first installation for a macOS TimeLapse Headend.
# Subsequent software changes must use the signed Headend update flow.

set -euo pipefail

log() { printf '[headend-bootstrap] %s\n' "$*"; }
die() { printf '[headend-bootstrap] ERROR: %s\n' "$*" >&2; exit 1; }

MODE="preflight"
CONFIG=""
REPO_URL=""
RELEASE_TAG=""
EXPECTED_COMMIT=""
DESTINATION=""
REPORT="${TMPDIR:-/tmp}/timelapse-headend-preflight.json"

while (( $# )); do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    --repo-url) REPO_URL="$2"; shift 2 ;;
    --release-tag) RELEASE_TAG="$2"; shift 2 ;;
    --expected-commit) EXPECTED_COMMIT="$2"; shift 2 ;;
    --destination) DESTINATION="$2"; shift 2 ;;
    --report) REPORT="$2"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage:
  bootstrap_headend_macos.sh --mode preflight --config environment.conf
  bootstrap_headend_macos.sh --mode stage --config environment.conf \
    --repo-url <github-url> --release-tag <signed-tag> \
    --expected-commit <full-sha> --destination <empty-directory>

Modes:
  preflight  Read-only coexistence and prerequisite inventory.
  stage      Preflight, fetch signed immutable release and run installer dry-run.

The script never changes package-manager software, macOS updates or existing services.
EOF
      exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[[ "$(uname -s)" == "Darwin" ]] || die "macOS is required"
[[ -n "$CONFIG" && -r "$CONFIG" ]] || die "--config must reference a readable environment file"
# shellcheck source=/dev/null
source "$CONFIG"
: "${TL_ENV:?TL_ENV is required}"
: "${TL_BACKEND_PORT:=8443}"
: "${TL_DOMAIN_BACKEND:?TL_DOMAIN_BACKEND is required}"
[[ "$TL_BACKEND_PORT" != 21 && "$TL_BACKEND_PORT" != 22 && "$TL_BACKEND_PORT" != 80 && "$TL_BACKEND_PORT" != 443 ]] \
  || die "TimeLapse must not bind reserved coexistence port $TL_BACKEND_PORT"

command_json() {
  local command="$1"
  if command -v "$command" >/dev/null 2>&1; then
    printf 'true'
  else
    printf 'false'
  fi
}

mkdir -p "$(dirname "$REPORT")"
python3 - "$REPORT" "$TL_ENV" "$TL_DOMAIN_BACKEND" "$TL_BACKEND_PORT" <<'PY'
import json, os, platform, socket, subprocess, sys
from datetime import datetime, timezone

report_path, environment, domain, backend_port = sys.argv[1:]

def output(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        return {"returncode": result.returncode, "stdout": result.stdout[-50000:], "stderr": result.stderr[-10000:]}
    except Exception as exc:
        return {"error": str(exc)}

listeners = output(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"])
launchdaemons = output(["find", "/Library/LaunchDaemons", "-maxdepth", "1", "-type", "f", "-name", "*.plist", "-print"])
brew = output(["brew", "list", "--versions"]) if output(["which", "brew"]).get("returncode") == 0 else {"available": False}
port_free = True
try:
    with socket.socket() as sock:
        sock.bind(("0.0.0.0", int(backend_port)))
except OSError:
    port_free = False

report = {
    "schema": "dk.froekjaer.timelapse.headend-preflight.v1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "read_only": True,
    "host": {"hostname": platform.node(), "macos": platform.mac_ver()[0], "architecture": platform.machine()},
    "requested": {"environment": environment, "domain": domain, "backend_port": int(backend_port)},
    "coexistence": {
        "backend_port_free": port_free,
        "reserved_ports_left_untouched": [21, 22, 80, 443],
        "listeners": listeners,
        "launch_daemons": launchdaemons,
        "homebrew_inventory": brew,
    },
    "policy": {
        "os_or_homebrew_upgrade_performed": False,
        "existing_apps_modified": False,
        "subsequent_changes_via_signed_update_flow": True,
    },
}
with open(report_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, ensure_ascii=False, indent=2)
print(json.dumps({"report": report_path, "backend_port_free": port_free}))
if not port_free:
    raise SystemExit(3)
PY

log "Preflight evidence written to $REPORT"
[[ "$MODE" == "preflight" ]] && exit 0
[[ "$MODE" == "stage" ]] || die "Unsupported mode: $MODE"
[[ -n "$REPO_URL" && -n "$RELEASE_TAG" && -n "$EXPECTED_COMMIT" && -n "$DESTINATION" ]] \
  || die "stage requires --repo-url, --release-tag, --expected-commit and --destination"
[[ "$EXPECTED_COMMIT" == [0-9a-fA-F]## ]] || die "--expected-commit must be a hexadecimal commit ID"
(( ${#EXPECTED_COMMIT} == 40 )) || die "--expected-commit must be the full 40-character SHA"
[[ ! -e "$DESTINATION" || -z "$(ls -A "$DESTINATION" 2>/dev/null)" ]] || die "Destination must be empty: $DESTINATION"

mkdir -p "$DESTINATION"
git -c protocol.file.allow=never init "$DESTINATION" >/dev/null
git -C "$DESTINATION" remote add origin "$REPO_URL"
git -C "$DESTINATION" fetch --depth=1 origin "refs/tags/$RELEASE_TAG:refs/tags/$RELEASE_TAG"
git -C "$DESTINATION" verify-tag "$RELEASE_TAG" >/dev/null \
  || die "Release tag is not trusted by the local GPG keyring: $RELEASE_TAG"
ACTUAL_COMMIT="$(git -C "$DESTINATION" rev-list -n1 "$RELEASE_TAG")"
[[ "$ACTUAL_COMMIT" == "$EXPECTED_COMMIT" ]] \
  || die "Release commit mismatch: expected $EXPECTED_COMMIT, got $ACTUAL_COMMIT"
git -C "$DESTINATION" checkout --detach "$EXPECTED_COMMIT" >/dev/null
git -C "$DESTINATION" status --porcelain | grep -q . && die "Staged release is not clean"

log "Verified signed release $RELEASE_TAG at $EXPECTED_COMMIT"
log "Running the legacy installer in dry-run only; it is not yet coexistence-safe for shared nginx"
"$DESTINATION/deploy/install/install_headend.sh" --config "$CONFIG" --dry-run
log "Staging complete. No packages, services, database or OS settings were changed."
