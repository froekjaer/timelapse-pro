#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — Node Agent Install (macOS / Mac Mini)
# Kør: sudo bash ~/Downloads/install_node_agent_macos.sh
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="$HOME/projects/timelapse-pro"
AGENT_SRC="$REPO/node-agent"
INSTALL_DIR="/opt/timelapse-node-agent"
CONF_DIR="/etc/timelapse"
CONF_FILE="$CONF_DIR/node-agent.conf"
PLIST_NAME="dk.froekjaer.timelapse-node-agent"
PLIST_PATH="/Library/LaunchDaemons/$PLIST_NAME.plist"
LOG_FILE="/var/log/timelapse-node-agent.log"
PYTHON="$(which python3)"
VENV="$INSTALL_DIR/venv"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
step() { echo -e "\n${BOLD}── $1 ──${NC}"; }

# Kræver root
[ "$(id -u)" = "0" ] || { echo "Kør med sudo"; exit 1; }
REAL_USER="${SUDO_USER:-$(logname)}"
REAL_HOME=$(eval echo "~$REAL_USER")
HEADEND_URL="https://timelapse.froekjaer.dk"
DEVICE_ID="TL-MACMINI-HEADEND-TEST-1"

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

if [ -f "$CONF_FILE" ]; then
    warn "$CONF_FILE eksisterer — springer over (slet den for at nulstille)"
else
    cat > "$CONF_FILE" << EOF
[agent]
device_id          = $DEVICE_ID
headend_url        = $HEADEND_URL
inventory_interval = 300
security_interval  = 60
security_lookback  = 120
EOF
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
echo "  Log       : tail -f $LOG_FILE"
echo "  Stop      : sudo launchctl stop $PLIST_NAME"
echo "  Start     : sudo launchctl start $PLIST_NAME"
echo ""
