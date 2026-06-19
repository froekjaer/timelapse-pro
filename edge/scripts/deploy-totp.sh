#!/bin/bash
# deploy-totp.sh — Deploy TOTP captive portal til edge (timelapse0101)
# Kør fra headend/Mac: bash edge/scripts/deploy-totp.sh
set -euo pipefail

EDGE="${EDGE_HOST:-192.168.86.134}"
EDGE_USER="${EDGE_USER:-orangepi}"
REMOTE="${EDGE_USER}@${EDGE}"
REMOTE_DIR="/opt/timelapse/edge/scripts"
CONFIG_SRC="edge/config/bt-config.yaml"
CONFIG_DST="/etc/timelapse/bt-config.yaml"

echo "=== Deploy TOTP captive portal til $REMOTE ==="

# 1. Kopier filer til /tmp (ingen sudo)
echo "[1/5] Kopierer filer til /tmp..."
scp edge/scripts/totp-service.py         "$REMOTE:/tmp/totp-service.py"
scp edge/scripts/gen-bt-cert.sh          "$REMOTE:/tmp/gen-bt-cert.sh"
scp edge/scripts/timelapse-captive.sh    "$REMOTE:/tmp/timelapse-captive.sh"
scp "$CONFIG_SRC"                        "$REMOTE:/tmp/bt-config.yaml"
scp edge/scripts/timelapse-captive.service "$REMOTE:/tmp/timelapse-captive.service"
scp edge/scripts/timelapse-totp.service    "$REMOTE:/tmp/timelapse-totp.service"

# 2–5. Alt sudo i ét interaktivt kald
echo "[2/5] Installerer på edgen (sudo — indtast password én gang)..."
ssh -t "$REMOTE" bash <<'ENDSSH'
set -e
REMOTE_DIR=/opt/timelapse/edge/scripts

echo "  → opretter mapper..."
sudo mkdir -p "$REMOTE_DIR" /etc/timelapse /etc/systemd/system

echo "  → kopierer scripts..."
sudo mv /tmp/totp-service.py /tmp/gen-bt-cert.sh /tmp/timelapse-captive.sh "$REMOTE_DIR/"
sudo chmod +x "$REMOTE_DIR/gen-bt-cert.sh" "$REMOTE_DIR/timelapse-captive.sh"

echo "  → kopierer config..."
sudo mv /tmp/bt-config.yaml /etc/timelapse/bt-config.yaml
sudo chmod 600 /etc/timelapse/bt-config.yaml

echo "  → installerer systemd services..."
sudo mv /tmp/timelapse-captive.service /tmp/timelapse-totp.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "  → genererer TLS cert..."
sudo bash "$REMOTE_DIR/gen-bt-cert.sh"

echo "  → aktiverer og starter services..."
sudo systemctl enable timelapse-captive timelapse-totp
sudo systemctl restart timelapse-captive timelapse-totp

echo ""
echo "=== Status ==="
sudo systemctl status timelapse-captive timelapse-totp --no-pager -l

echo ""
echo "=== iptables TL_MGMT chain ==="
sudo bash "$REMOTE_DIR/timelapse-captive.sh" status
ENDSSH
echo ""
echo "✓ Deploy fuldført"
echo "  Test: Forbind telefon via BT PAN → åbn browser → https://192.168.42.1:8443"
echo "  TOTP secret (factory default): JBSWY3DPEHPK3PXP"
echo "  QR-kode: otpauth://totp/TimeLapse%20Pro:factory-default?secret=JBSWY3DPEHPK3PXP&issuer=TimeLapse%20Pro"
