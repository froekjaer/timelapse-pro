#!/bin/bash
# timelapse-captive.sh — iptables captive portal for br-bt
#
# Design:
#   - TL_MGMT chain: whitelistede klienter (tilføjes af totp-service.py ved login)
#   - Alt på br-bt blokeres undtagen den eksplicitte HTTPS management-port
#   - Ingen NAT/redirect på TCP 80, 443 eller 8080
#   - RFC1918 WiFi-adgang tillades direkte (ingen TOTP via WiFi)
#
# Kaldes fra timelapse-captive.service ved boot (start/stop)

set -euo pipefail

BT_BRIDGE="br-bt"
BT_IP="192.168.42.1"
HTTPS_PORT="8443"
CHAIN="TL_MGMT"

cmd="${1:-start}"

flush_chain() {
    iptables -F "$CHAIN" 2>/dev/null || true
    iptables -D FORWARD -i "$BT_BRIDGE" -j "$CHAIN" 2>/dev/null || true
    iptables -D INPUT   -i "$BT_BRIDGE" -j "$CHAIN" 2>/dev/null || true
    iptables -X "$CHAIN" 2>/dev/null || true
    # Fjern redirects fra ældre installationer. Nye installationer opretter
    # ingen NAT-regler på 80/443/8080.
    iptables -t nat -D PREROUTING -i "$BT_BRIDGE" -p tcp --dport 80 \
        -j REDIRECT --to-port 8080 2>/dev/null || true
    iptables -t nat -D PREROUTING -i "$BT_BRIDGE" -p tcp --dport 443 \
        -j REDIRECT --to-port "$HTTPS_PORT" 2>/dev/null || true
}

case "$cmd" in
start)
    echo "[captive] Sætter iptables captive portal op..."

    # Oprydning først (idempotent)
    flush_chain

    # Opret whitelist chain
    iptables -N "$CHAIN"

    # Tillad altid loopback og etablerede forbindelser
    iptables -A "$CHAIN" -i lo -j RETURN
    iptables -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

    # Tillad DHCP (port 67/68 UDP) — nødvendigt for at klienten får IP
    iptables -A "$CHAIN" -i "$BT_BRIDGE" -p udp --dport 67 -j ACCEPT
    iptables -A "$CHAIN" -i "$BT_BRIDGE" -p udp --dport 68 -j ACCEPT

    # Tillad DNS (port 53) — dnsmasq på br-bt
    iptables -A "$CHAIN" -i "$BT_BRIDGE" -p udp --dport 53 -j ACCEPT
    iptables -A "$CHAIN" -i "$BT_BRIDGE" -p tcp --dport 53 -j ACCEPT

    # Tillad adgang til TOTP-service på dens dedikerede HTTPS-port.
    iptables -A "$CHAIN" -i "$BT_BRIDGE" -p tcp -d "$BT_IP" --dport "$HTTPS_PORT" -j ACCEPT

    # Standard: DROP alt andet (whitelist tilføjes dynamisk af totp-service.py)
    iptables -A "$CHAIN" -i "$BT_BRIDGE" -j DROP

    # Kobl chain til INPUT og FORWARD
    iptables -I INPUT   1 -i "$BT_BRIDGE" -j "$CHAIN"
    iptables -I FORWARD 1 -i "$BT_BRIDGE" -j "$CHAIN"

    echo "[captive] Lokal management aktiv på https://$BT_IP:$HTTPS_PORT (ingen port-redirect)"
    ;;

stop)
    echo "[captive] Fjerner iptables captive portal..."
    flush_chain
    echo "[captive] Fjernet"
    ;;

status)
    echo "=== $CHAIN chain ==="
    iptables -L "$CHAIN" -n -v 2>/dev/null || echo "(chain eksisterer ikke)"
    echo ""
    echo "=== NAT PREROUTING (br-bt) ==="
    iptables -t nat -L PREROUTING -n -v | grep "$BT_BRIDGE" || echo "(ingen regler)"
    ;;

*)
    echo "Brug: $0 {start|stop|status}" >&2
    exit 1
    ;;
esac
