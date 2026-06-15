#!/usr/bin/env bash
# ============================================================================
# TimeLapse Pro — Edge Installer for NVIDIA Jetson Orin Nano
# ============================================================================
# Kører oven på et eksisterende JetPack 6.x system.
# Installerer edge-agenten, opsætter systemd-services og bootstrap.
#
# Krav:
#   - JetPack 6.0+ installeret via NVIDIA SDK Manager
#   - Internet-adgang ELLER headend-signeret offline artifact
#   - Køres som root: sudo bash install_timelapse_edge.sh
#
# Brug:
#   sudo bash install_timelapse_edge.sh \
#       --headend-url https://timelapse.froekjaer.dk/api \
#       --bootstrap-token <token>
#
# ============================================================================
set -euo pipefail

# ── Farver til output ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}[INSTALL]${NC} $*"; }
ok()   { echo -e "${GREEN}[  OK  ]${NC} $*"; }
warn() { echo -e "${YELLOW}[ WARN ]${NC} $*"; }
err()  { echo -e "${RED}[ FAIL ]${NC} $*"; exit 1; }

# ── Argumenter ────────────────────────────────────────────────────────────────
HEADEND_URL=""
BOOTSTRAP_TOKEN=""
REPO_DIR=""   # Lokal kopi af timelapse-pro (valgfri — hentes ellers fra headend)

while [[ $# -gt 0 ]]; do
    case "$1" in
        --headend-url)      HEADEND_URL="$2";      shift 2 ;;
        --bootstrap-token)  BOOTSTRAP_TOKEN="$2";  shift 2 ;;
        --repo-dir)         REPO_DIR="$2";         shift 2 ;;
        *) err "Ukendt argument: $1" ;;
    esac
done

[[ -z "$HEADEND_URL" ]]      && err "--headend-url er påkrævet"
[[ -z "$BOOTSTRAP_TOKEN" ]]  && err "--bootstrap-token er påkrævet"

# ── Root-check ────────────────────────────────────────────────────────────────
[[ "$EUID" -ne 0 ]] && err "Kræver root: sudo bash $0 $*"

# ── JetPack-check ─────────────────────────────────────────────────────────────
log "Verificerer JetPack-installation..."
if [[ ! -f /etc/nv_tegra_release ]] && [[ ! -f /etc/nv_jetson_release ]]; then
    warn "Ingen /etc/nv_tegra_release — er JetPack korrekt installeret?"
else
    JETPACK_VER=$(head -1 /etc/nv_tegra_release 2>/dev/null || head -1 /etc/nv_jetson_release 2>/dev/null || echo "ukendt")
    ok "JetPack detekteret: $JETPACK_VER"
fi

CUDA_VER=$(nvcc --version 2>/dev/null | grep -oP 'release \K[\d.]+' || echo "ikke fundet")
ok "CUDA: $CUDA_VER"

# ── Stier ─────────────────────────────────────────────────────────────────────
INSTALL_BASE="/opt/timelapse"
AGENT_DIR="$INSTALL_BASE/edge"
VENV_DIR="$INSTALL_BASE/venv"
DATA_DIR="/data"
CONFIG_DIR="/etc/timelapse"
KEYS_DIR="$CONFIG_DIR/device_keys"

# ── System-pakker ─────────────────────────────────────────────────────────────
log "Installerer system-pakker..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    openssh-client openssh-server \
    curl rsync iproute2 iputils-ping \
    2>/dev/null
ok "System-pakker installeret"

# ── Bruger ────────────────────────────────────────────────────────────────────
if ! id timelapse &>/dev/null; then
    log "Opretter timelapse-bruger..."
    useradd -m -s /bin/bash timelapse
    passwd -l timelapse
    ok "Bruger 'timelapse' oprettet"
fi

# ── Mappestruktur ─────────────────────────────────────────────────────────────
log "Opretter mappestruktur..."
mkdir -p "$AGENT_DIR" "$VENV_DIR" "$DATA_DIR" "$CONFIG_DIR" "$KEYS_DIR" \
         /run/timelapse
chown -R timelapse:timelapse "$INSTALL_BASE" "$DATA_DIR" "$CONFIG_DIR" /run/timelapse
chmod 700 "$KEYS_DIR"
ok "Mapper oprettet"

# ── Python venv ───────────────────────────────────────────────────────────────
log "Opretter Python venv og installerer pakker..."
python3 -m venv "$VENV_DIR"

# Base-pakker (slim — opencv installeres separat med CUDA)
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet \
    pyyaml>=6.0 \
    requests>=2.31.0 \
    paramiko>=3.3.0 \
    cryptography>=41.0 \
    tzdata>=2024.1
ok "Python pakker installeret"

# ── Edge-kode ─────────────────────────────────────────────────────────────────
if [[ -n "$REPO_DIR" ]] && [[ -d "$REPO_DIR/edge" ]]; then
    log "Kopierer edge-kode fra lokal repo: $REPO_DIR/edge"
    rsync -a --delete "$REPO_DIR/edge/" "$AGENT_DIR/"
    ok "Edge-kode kopieret"
else
    warn "Ingen --repo-dir angivet. Edge-kode skal installeres manuelt i $AGENT_DIR"
    warn "Kør efter enrollment: headend vil pushe edge-kode via artifact update"
fi

chown -R timelapse:timelapse "$AGENT_DIR"

# ── SSH hardening ──────────────────────────────────────────────────────────────
log "SSH hardening..."
sed -i \
    -e 's/^#\?PermitRootLogin.*/PermitRootLogin no/' \
    -e 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
    /etc/ssh/sshd_config
mkdir -p /run/sshd
ok "SSH hardenet"

# ── Bootstrap config ──────────────────────────────────────────────────────────
log "Skriver bootstrap.yaml..."
cat > "$CONFIG_DIR/bootstrap.yaml" <<EOF
headend_url: "${HEADEND_URL}"
bootstrap_token: "${BOOTSTRAP_TOKEN}"
EOF
chmod 600 "$CONFIG_DIR/bootstrap.yaml"
chown root:root "$CONFIG_DIR/bootstrap.yaml"
ok "bootstrap.yaml skrevet"

# ── Systemd services ──────────────────────────────────────────────────────────
log "Installerer systemd services..."

# Bootstrap service
cat > /etc/systemd/system/timelapse-bootstrap.service <<'UNIT'
[Unit]
Description=TimeLapse Pro — First-boot Enrollment Agent
After=network-online.target
Wants=network-online.target
Before=timelapse-edge.service
ConditionPathExists=!/etc/timelapse/.enrolled

[Service]
Type=oneshot
RemainAfterExit=no
User=root
WorkingDirectory=/opt/timelapse/edge
ExecStart=/opt/timelapse/venv/bin/python /opt/timelapse/edge/scripts/bootstrap_agent.py
TimeoutStartSec=600
StandardOutput=journal
StandardError=journal
SyslogIdentifier=timelapse-bootstrap
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT

# Edge agent service (kopieres fra edge/scripts hvis tilgængeligt)
if [[ -f "$AGENT_DIR/scripts/timelapse-edge.service" ]]; then
    cp "$AGENT_DIR/scripts/timelapse-edge.service" /etc/systemd/system/
    ok "timelapse-edge.service kopieret fra agent-dir"
else
    cat > /etc/systemd/system/timelapse-edge.service <<'UNIT'
[Unit]
Description=TimeLapse Pro Edge Agent
After=network-online.target timelapse-bootstrap.service
Wants=network-online.target
ConditionPathExists=/etc/timelapse/.enrolled

[Service]
Type=notify
User=timelapse
Group=timelapse
WorkingDirectory=/opt/timelapse/edge
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/opt/timelapse/edge
ExecStart=/opt/timelapse/venv/bin/python /opt/timelapse/edge/agent.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
WatchdogSec=120
NotifyAccess=main
StandardOutput=journal
StandardError=journal
SyslogIdentifier=timelapse-edge
NoNewPrivileges=yes
ReadWritePaths=/data /opt/timelapse/edge /run/timelapse

[Install]
WantedBy=multi-user.target
UNIT
    ok "timelapse-edge.service skrevet (fallback)"
fi

systemctl daemon-reload
systemctl enable timelapse-bootstrap.service
ok "Services installeret og aktiveret"

# ── opencv med CUDA (valgfri, tager lang tid) ─────────────────────────────────
if command -v nvcc &>/dev/null; then
    log "NVIDIA CUDA fundet — installerer opencv-python-headless (med CUDA support)..."
    warn "Dette tager 10-40 minutter første gang (kompilering fra source)"
    # Brug pre-built wheel fra jetson-zoo hvis tilgængeligt
    JETSON_WHEEL_URL="https://github.com/Qengineering/Install-OpenCV-Jetson-Nano/releases"
    warn "Kør manuelt: $VENV_DIR/bin/pip install opencv-python-headless"
    warn "For CUDA-accelereret opencv, se: https://github.com/Qengineering/Install-OpenCV-Jetson-Nano"
fi

# ── Afslutning ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  TimeLapse Pro Edge installeret på Jetson Orin Nano!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "  Headend URL:      $HEADEND_URL"
echo "  Config dir:       $CONFIG_DIR"
echo "  Agent dir:        $AGENT_DIR"
echo ""
echo "  Næste trin:"
echo "  1. Genstart boardet: sudo reboot"
echo "  2. timelapse-bootstrap.service kører automatisk ved boot"
echo "  3. Enheden vises som 'Ikke-tildelt' i headend UI"
echo "  4. Gå til headend UI → Provisioning → Tildel til site"
echo ""

# Start bootstrap nu (uden reboot)
read -p "Start bootstrap med det samme (y/N)? " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log "Starter timelapse-bootstrap.service..."
    systemctl start timelapse-bootstrap.service
    journalctl -fu timelapse-bootstrap.service --no-pager -n 50 &
    sleep 30
    kill %1 2>/dev/null || true
fi
