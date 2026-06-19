#!/bin/bash
# timelapse-captive.sh — iptables captive portal for br-bt
#
# Design:
#   - TL_MGMT chain: whitelistede klienter (tilføjes af totp-service.py ved login)
#   - Alt på br-bt blokeres undtagen port 80 + 8443
#   - Port 80 redirectes til 8443 (HTTPS TOTP login)
#   - RFC1918 WiFi-adgang tillades direkte (ingen TOTP via WiFi)
#
# Kaldes fra timelapse-captive.service ved boot (start/stop)

set -euo pipefail

BT_BRIDGE="br-bt"
BT_IP="192.168.42.1"
HTTPS_PORT="8443"
HTTP_PORT="8080"
CHAIN="TL_MGMT"

cmd="${1:-start}"

flush_chain() {
    iptables -F "$CHAIN" 2>/dev/null || true
    iptables -D FORWARD -i "$BT_BRIDGE" -j "$CHAIN" 2>/dev/null || true
    iptables -D INPUT   -i "$BT_BRIDGE" -j "$CHAIN" 2>/dev/null || true
    iptables -X "$CHAIN" 2>/dev/null || true
    # Fjern NAT redirect
    iptables -t nat -D PREROUTING -i "$BT_BRIDGE" -p tcp --dport 80 \
        -j REDIRECT --to-port "$HTTP_PORT" 2>/dev/null || true
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

    # Tillad adgang til TOTP-service (HTTP redirect + HTTPS login)
    iptables -A "$CHAIN" -i "$BT_BRIDGE" -p tcp -d "$BT_IP" --dport "$HTTP_PORT" -j ACCEPT
    iptables -A "$CHAIN" -i "$BT_BRIDGE" -p tcp -d "$BT_IP" --dport "$HTTPS_PORT" -j ACCEPT

    # Standard: DROP alt andet (whitelist tilføjes dynamisk af totp-service.py)
    iptables -A "$CHAIN" -i "$BT_BRIDGE" -j DROP

    # Kobl chain til INPUT og FORWARD
    iptables -I INPUT   1 -i "$BT_BRIDGE" -j "$CHAIN"
    iptables -I FORWARD 1 -i "$BT_BRIDGE" -j "$CHAIN"

    # NAT: port 80 → HTTPS TOTP service (direkte, ingen separat HTTP-process)
    # Browser vil få TLS handshake og kan se cert-advarsel — acceptable for lokal portal
    iptables -t nat -A PREROUTING -i "$BT_BRIDGE" -p tcp --dport 80 \
        -j REDIRECT --to-port "$HTTPS_PORT"

    # NAT: port 443 → lokal HTTPS TOTP service
    iptables -t nat -A PREROUTING -i "$BT_BRIDGE" -p tcp --dport 443 \
        -j REDIRECT --to-port "$HTTPS_PORT"

    echo "[captive] Captive portal aktiv — alt blokeret undtagen DHCP/DNS/TOTP"
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
