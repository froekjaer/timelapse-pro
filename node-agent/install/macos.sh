#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — Node Agent Install (macOS / Mac Mini)
# Kør: sudo bash node-agent/install/macos.sh --device-id <id> --headend-url <url> --api-token-file <fil>
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

AGENT_SRC="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="/opt/timelapse-node-agent"
CONF_DIR="/etc/timelapse"
CONF_FILE="$CONF_DIR/node-agent.conf"
PLIST_NAME="dk.froekjaer.timelapse-node-agent"
PLIST_PATH="/Library/LaunchDaemons/$PLIST_NAME.plist"
LOG_FILE="/var/log/timelapse-node-agent.log"
VENV="$INSTALL_DIR/venv"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
step() { echo -e "\n${BOLD}── $1 ──${NC}"; }

# Kræver root
[ "$(id -u)" = "0" ] || { echo "Kør med sudo"; exit 1; }
REAL_USER="${SUDO_USER:-$(logname)}"
REAL_HOME=$(eval echo "~$REAL_USER")
REAL_GROUP=$(id -gn "$REAL_USER")
DEVICE_ID=""
HEADEND_URL=""
API_TOKEN_FILE=""
REPLACE_CONFIG=0

usage() {
    cat <<'EOF'
Usage: sudo node-agent/install/macos.sh \
  --device-id TL-HEADEND-STAGING-1 \
  --headend-url https://staging.timelapse-pro.dk:8443 \
  --api-token-file /secure/path/api-token [--replace-config]

No environment-specific defaults are used. The token file must only be readable
by its owner and is never copied into logs or process arguments.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --device-id) DEVICE_ID="${2:-}"; shift 2 ;;
        --headend-url) HEADEND_URL="${2:-}"; shift 2 ;;
        --api-token-file) API_TOKEN_FILE="${2:-}"; shift 2 ;;
        --replace-config) REPLACE_CONFIG=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Ukendt argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[ -n "$DEVICE_ID" ] || { echo "--device-id er påkrævet" >&2; exit 2; }
case "$DEVICE_ID" in TL-*) ;; *) echo "Ugyldigt device-id: $DEVICE_ID" >&2; exit 2 ;; esac
[ -n "$HEADEND_URL" ] || { echo "--headend-url er påkrævet" >&2; exit 2; }
case "$HEADEND_URL" in https://*) ;; *) echo "--headend-url skal bruge https" >&2; exit 2 ;; esac
[ -r "$API_TOKEN_FILE" ] || { echo "--api-token-file skal være en læsbar fil" >&2; exit 2; }
API_TOKEN="$(tr -d '\r\n' < "$API_TOKEN_FILE")"
[ -n "$API_TOKEN" ] || { echo "API-tokenfilen er tom" >&2; exit 2; }
PYTHON="$(command -v python3)"

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════╗"
echo "║  TimeLapse Pro — Node Agent (macOS install)  ║"
echo "╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Kopiér agent-filer ────────────────────────────────────────────────────
step "Installerer agent-filer"
mkdir -p "$INSTALL_DIR/collectors"
cp "$AGENT_SRC/agent.py"                  "$INSTALL_DIR/"
cp "$AGENT_SRC/config.py"                 "$INSTALL_DIR/"
cp "$AGENT_SRC/transport.py"              "$INSTALL_DIR/"
cp "$AGENT_SRC/collectors/inventory.py"   "$INSTALL_DIR/collectors/"
cp "$AGENT_SRC/collectors/security.py"    "$INSTALL_DIR/collectors/"
touch "$INSTALL_DIR/collectors/__init__.py"
SOURCE_COMMIT="$(git -C "$AGENT_SRC/.." rev-parse HEAD 2>/dev/null || true)"
if [[ "$SOURCE_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]]; then
    printf '{"schema":"timelapse.node.release.v1","source_commit":"%s"}\n' \
        "$SOURCE_COMMIT" > "$INSTALL_DIR/.timelapse-release.json"
    chmod 0444 "$INSTALL_DIR/.timelapse-release.json"
fi
ok "Agent-filer kopieret til $INSTALL_DIR"

# ── Venv ──────────────────────────────────────────────────────────────────
step "Python venv"
if [ ! -d "$VENV" ]; then
    "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
ok "Venv klar: $VENV"

# ── Konfiguration ─────────────────────────────────────────────────────────
step "Konfigurationsfil"
mkdir -p "$CONF_DIR"

if [ -f "$CONF_FILE" ] && [ "$REPLACE_CONFIG" != "1" ]; then
    warn "$CONF_FILE eksisterer — brug --replace-config for kontrolleret udskiftning"
    exit 3
else
    CONF_TMP="$(mktemp "$CONF_DIR/node-agent.conf.XXXXXX")"
    cat > "$CONF_TMP" << EOF
[agent]
device_id          = $DEVICE_ID
headend_url        = $HEADEND_URL
api_token          = $API_TOKEN
inventory_interval = 300
security_interval  = 60
security_lookback  = 120
EOF
    chown root:"$REAL_GROUP" "$CONF_TMP"
    chmod 640 "$CONF_TMP"
    mv -f "$CONF_TMP" "$CONF_FILE"
    ok "Konfiguration skrevet: $CONF_FILE"
fi

# ── Launchd plist ─────────────────────────────────────────────────────────
step "Launchd plist"
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV/bin/python3</string>
        <string>$INSTALL_DIR/agent.py</string>
        <string>--config</string>
        <string>$CONF_FILE</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>UserName</key>
    <string>$REAL_USER</string>
    <key>GroupName</key>
    <string>$REAL_GROUP</string>
    <key>StandardOutPath</key>
    <string>$LOG_FILE</string>
    <key>StandardErrorPath</key>
    <string>$LOG_FILE</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF
ok "Plist skrevet: $PLIST_PATH"

# ── Start service ─────────────────────────────────────────────────────────
step "Starter node agent"
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load   "$PLIST_PATH"
sleep 3

if launchctl list | grep -q "$PLIST_NAME"; then
    ok "Node agent kører"
else
    warn "Node agent kører muligvis ikke — tjek: tail -f $LOG_FILE"
fi

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════╗"
echo "║        Node Agent installeret! 🎉           ║"
echo "╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Device ID : $DEVICE_ID"
echo "  Headend   : $HEADEND_URL"
echo "  Log       : tail -f $LOG_FILE"
echo "  Stop      : sudo launchctl stop $PLIST_NAME"
echo "  Start     : sudo launchctl start $PLIST_NAME"
echo ""
