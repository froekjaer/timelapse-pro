#!/bin/bash
# deploy-totp.sh — Deploy TOTP captive portal til edge (timelapse0101)
# Kør fra headend/Mac: bash edge/scripts/deploy-totp.sh
set -euo pipefail

EDGE="timelapse0101"
REMOTE_DIR="/opt/timelapse/edge/scripts"
CONFIG_SRC="edge/config/bt-config.yaml"
CONFIG_DST="/etc/timelapse/bt-config.yaml"

echo "=== Deploy TOTP captive portal til $EDGE ==="

# 1. Sync scripts
echo "[1/5] Kopierer scripts..."
ssh "$EDGE" "mkdir -p $REMOTE_DIR"
scp edge/scripts/totp-service.py    "$EDGE:$REMOTE_DIR/"
scp edge/scripts/gen-bt-cert.sh     "$EDGE:$REMOTE_DIR/"
scp edge/scripts/timelapse-captive.sh "$EDGE:$REMOTE_DIR/"
ssh "$EDGE" "chmod +x $REMOTE_DIR/gen-bt-cert.sh $REMOTE_DIR/timelapse-captive.sh"

# 2. Deploy config
echo "[2/5] Kopierer bt-config.yaml..."
ssh "$EDGE" "mkdir -p /etc/timelapse"
scp "$CONFIG_SRC" "$EDGE:$CONFIG_DST"
ssh "$EDGE" "chmod 600 $CONFIG_DST"

# 3. Deploy systemd services
echo "[3/5] Installerer systemd services..."
scp edge/scripts/timelapse-captive.service "$EDGE:/etc/systemd/system/"
scp edge/scripts/timelapse-totp.service    "$EDGE:/etc/systemd/system/"
ssh "$EDGE" "systemctl daemon-reload"

# 4. Generer TLS cert
echo "[4/5] Genererer TLS cert..."
ssh "$EDGE" "bash $REMOTE_DIR/gen-bt-cert.sh"

# 5. Aktiver og start services
echo "[5/5] Aktiverer services..."
ssh "$EDGE" "systemctl enable timelapse-captive timelapse-totp"
ssh "$EDGE" "systemctl restart timelapse-captive timelapse-totp"

echo ""
echo "=== Status ==="
ssh "$EDGE" "systemctl status timelapse-captive timelapse-totp --no-pager -l"
echo ""
echo "=== iptables TL_MGMT chain ==="
ssh "$EDGE" "bash $REMOTE_DIR/timelapse-captive.sh status"
echo ""
echo "✓ Deploy fuldført"
echo "  Test: Forbind telefon via BT PAN → åbn browser → https://192.168.42.1:8443"
echo "  TOTP secret (factory default): JBSWY3DPEHPK3PXP"
echo "  QR-kode: otpauth://totp/TimeLapse%20Pro:factory-default?secret=JBSWY3DPEHPK3PXP&issuer=TimeLapse%20Pro"
