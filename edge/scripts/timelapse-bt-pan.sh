#!/bin/bash
# TimeLapse Pro — Bluetooth PAN setup
# Kører ved boot via timelapse-bt-pan.service
# Board: OrangePi 4 Pro (Allwinner A733/sun60iw2, AIC8800 BT chip)
#
# AIC8800 notes:
#   - hciattach_opi sætter placeholder MAC 10:11:12:13:14:15
#   - Vendor HCI cmd 0xfc70 overskriver MAC runtime (persisterer til chip reset)
#   - bluetoothctl discoverable on gen-aktiverer secure-conn — accepteret, bt-autoagent håndterer
#   - NAP registreres og holdes åben af bt-autoagent.py (D-Bus daemon)

set -e

BT_CONFIG="/etc/timelapse/bt-pan.conf"
BRIDGE="br-bt"
BRIDGE_IP="192.168.42.1"
DHCP_RANGE_START="192.168.42.10"
DHCP_RANGE_END="192.168.42.50"
DHCP_LEASE="12h"
DNSMASQ_PID="/run/timelapse/dnsmasq-bt.pid"
DEVICE_NAME="$(hostname)"

# --- Læs konfiguration ---
BT_MAC=""
if [ -f "$BT_CONFIG" ]; then
    BT_MAC=$(grep -E "^bt_mac\s*=" "$BT_CONFIG" | awk -F'=' '{print $2}' | tr -d ' ')
fi

# Hvis ingen MAC konfigureret: aflæs fra wlan0 + 1 (AIC8800 konvention)
if [ -z "$BT_MAC" ]; then
    WLAN_MAC=$(ip link show wlan0 2>/dev/null | grep "link/ether" | awk '{print $2}')
    if [ -n "$WLAN_MAC" ]; then
        LAST=$(printf "%d" "0x$(echo "$WLAN_MAC" | awk -F: '{print $6}')")
        LAST=$(( (LAST + 1) % 256 ))
        BT_MAC=$(echo "$WLAN_MAC" | awk -F: -v last="$(printf '%02x' $LAST)" \
            '{print $1":"$2":"$3":"$4":"$5":"last}')
    fi
fi

log() { echo "[timelapse-bt-pan] $*"; }

# --- 1. Vent på hci0 ---
log "Venter på hci0..."
for i in $(seq 1 30); do
    hciconfig hci0 >/dev/null 2>&1 && break
    sleep 1
done
hciconfig hci0 >/dev/null 2>&1 || { log "FEJL: hci0 ikke fundet"; exit 1; }

# --- 2. Sæt korrekt BT MAC via AIC vendor command 0xfc70 ---
if [ -n "$BT_MAC" ]; then
    log "Sætter BD Address: $BT_MAC"
    B1=$(echo "$BT_MAC" | awk -F: '{print $6}')
    B2=$(echo "$BT_MAC" | awk -F: '{print $5}')
    B3=$(echo "$BT_MAC" | awk -F: '{print $4}')
    B4=$(echo "$BT_MAC" | awk -F: '{print $3}')
    B5=$(echo "$BT_MAC" | awk -F: '{print $2}')
    B6=$(echo "$BT_MAC" | awk -F: '{print $1}')
    hcitool cmd 0x3f 0x0070 "$B1" "$B2" "$B3" "$B4" "$B5" "$B6" >/dev/null 2>&1 || \
        log "ADVARSEL: MAC-kommando fejlede (chip måske ikke AIC8800)"
fi

# --- 3. Bluetooth controller op ---
timeout 5 bluetoothctl power on >/dev/null 2>&1 || true

# --- 4. IO capability + discoverable ---
timeout 5 btmgmt io-cap 4 >/dev/null 2>&1 || true   # KeyboardDisplay: agent håndterer confirmation
timeout 5 bluetoothctl discoverable-timeout 0 >/dev/null 2>&1 || true
timeout 5 bluetoothctl discoverable on >/dev/null 2>&1 || true
timeout 5 bluetoothctl pairable on >/dev/null 2>&1 || true

# --- 5. BT bridge ---
ip link add "$BRIDGE" type bridge 2>/dev/null || true
ip addr add "$BRIDGE_IP/24" dev "$BRIDGE" 2>/dev/null || true
ip link set "$BRIDGE" up

# --- 6. NAP registreres af timelapse-bt-agent.service (bt-autoagent.py) ---
# bt-autoagent.py holder D-Bus-forbindelsen åben — busctl-registrering virker ikke
log "NAP håndteres af bt-autoagent.py (timelapse-bt-agent.service)"

# --- 7. DHCP på bridge (port 0 = ingen DNS) ---
mkdir -p /run/timelapse /var/log.hdd/timelapse
pkill -f "dnsmasq.*$BRIDGE" 2>/dev/null || true
sleep 1
dnsmasq \
    --interface="$BRIDGE" \
    --bind-interfaces \
    --dhcp-range="$DHCP_RANGE_START,$DHCP_RANGE_END,$DHCP_LEASE" \
    --port=0 \
    --pid-file="$DNSMASQ_PID" \
    --log-facility=/var/log.hdd/timelapse/dnsmasq-bt.log

ACTUAL_MAC=$(hciconfig hci0 2>/dev/null | grep "BD Address" | awk '{print $3}')
log "BT PAN klar. BD Address: ${ACTUAL_MAC:-ukendt}  Bridge: $BRIDGE_IP"
log "Enhedsnavn: $DEVICE_NAME"
