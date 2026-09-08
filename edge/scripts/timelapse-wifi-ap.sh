#!/bin/bash
# TimeLapse Pro - isolated WiFi AP for local technician access.
# A live client association always wins. If it drops, this fallback AP starts.
set -euo pipefail

AP_IF="${TIMELAPSE_WIFI_AP_INTERFACE:-wlan0}"
AP_ADDR="${TIMELAPSE_WIFI_AP_ADDRESS:-192.168.43.1}"
AP_RANGE_START="${TIMELAPSE_WIFI_AP_DHCP_START:-192.168.43.10}"
AP_RANGE_END="${TIMELAPSE_WIFI_AP_DHCP_END:-192.168.43.50}"
AP_COUNTRY="${TIMELAPSE_WIFI_AP_COUNTRY:-DK}"
AP_DIR="/run/timelapse/wifi-ap"
HOSTAPD_CONF="$AP_DIR/hostapd.conf"
DNSMASQ_CONF="$AP_DIR/dnsmasq.conf"
HOSTAPD_PID="$AP_DIR/hostapd.pid"
DNSMASQ_PID="$AP_DIR/dnsmasq.pid"
AP_ACTIVE="$AP_DIR/active"
CHAIN="TL_WIFI_MGMT"

log() { echo "[timelapse-wifi-ap] $*"; }

configured_client_profile() {
    # A profile tells us that this interface is intended for router WiFi.
    if [[ -f /etc/netplan/60-wifi.yaml ]] && grep -Eq '^[[:space:]]*access-points:' /etc/netplan/60-wifi.yaml; then return 0; fi
    if [[ -f /etc/wpa_supplicant/wpa_supplicant.conf ]] && grep -Eq '^[[:space:]]*network[[:space:]]*=' /etc/wpa_supplicant/wpa_supplicant.conf; then return 0; fi
    if command -v nmcli >/dev/null 2>&1 && nmcli -t -f connection.interface-name,type connection show 2>/dev/null | grep -E '(^|:)wlan0:(wifi|802-11-wireless)$' >/dev/null; then return 0; fi
    return 1
}

client_wifi_active() {
    if command -v iw >/dev/null 2>&1; then
        iw dev "$AP_IF" link 2>/dev/null | grep -q '^Connected to '
        return $?
    fi
    if command -v nmcli >/dev/null 2>&1; then
        nmcli -t -f DEVICE,STATE device status 2>/dev/null | grep -Eq "^${AP_IF}:connected$"
        return $?
    fi
    # With a configured profile but no trustworthy link inspection, do not
    # risk taking over the interface and breaking the existing connection.
    configured_client_profile
}

device_id() {
    local path=/opt/timelapse/edge/bootstrap.yaml value
    [[ -r "$path" ]] || return 1
    value=$(awk -F: '/^[[:space:]]*device_id[[:space:]]*:/ {print $2; exit}' "$path" | tr -d ' "\t\r')
    [[ "$value" =~ ^TL-[A-Za-z0-9_-]+$ ]] || return 1
    printf '%s\n' "$value"
}

flush_firewall() {
    iptables -D INPUT -i "$AP_IF" -j "$CHAIN" 2>/dev/null || true
    iptables -D FORWARD -i "$AP_IF" -j "$CHAIN" 2>/dev/null || true
    iptables -F "$CHAIN" 2>/dev/null || true
    iptables -X "$CHAIN" 2>/dev/null || true
}

start() {
    if client_wifi_active; then log "Router-WiFi er aktiv; AP holdes slukket"; exit 0; fi
    if configured_client_profile; then log "Router-WiFi er offline; starter lokalt fejlsøgnings-AP"; fi
    local ssid
    ssid=$(device_id) || { log "FEJL: device_id mangler eller er ugyldigt"; exit 1; }
    command -v hostapd >/dev/null 2>&1 || { log "FEJL: hostapd mangler"; exit 1; }
    command -v dnsmasq >/dev/null 2>&1 || { log "FEJL: dnsmasq mangler"; exit 1; }
    mkdir -p "$AP_DIR" /var/log.hdd/timelapse
    ip link set "$AP_IF" down 2>/dev/null || true
    ip addr flush dev "$AP_IF" 2>/dev/null || true
    ip addr add "$AP_ADDR/24" dev "$AP_IF"
    ip link set "$AP_IF" up
    printf 'interface=%s\ndriver=nl80211\nssid=%s\ncountry_code=%s\nhw_mode=g\nchannel=1\nieee80211n=1\nauth_algs=1\nwmm_enabled=1\nwpa=0\n' "$AP_IF" "$ssid" "$AP_COUNTRY" > "$HOSTAPD_CONF"
    chmod 600 "$HOSTAPD_CONF"
    printf 'interface=%s\nbind-interfaces\nport=0\ndhcp-range=%s,%s,12h\ndhcp-authoritative\npid-file=%s\n' "$AP_IF" "$AP_RANGE_START" "$AP_RANGE_END" "$DNSMASQ_PID" > "$DNSMASQ_CONF"
    chmod 600 "$DNSMASQ_CONF"
    flush_firewall
    iptables -N "$CHAIN"
    iptables -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    iptables -A "$CHAIN" -i "$AP_IF" -p udp --dport 67 -j ACCEPT
    iptables -A "$CHAIN" -i "$AP_IF" -p udp --dport 68 -j ACCEPT
    iptables -A "$CHAIN" -i "$AP_IF" -p tcp --dport 8443 -d "$AP_ADDR" -j ACCEPT
    iptables -A "$CHAIN" -i "$AP_IF" -j DROP
    iptables -I INPUT 1 -i "$AP_IF" -j "$CHAIN"
    iptables -I FORWARD 1 -i "$AP_IF" -j "$CHAIN"
    sysctl -w net.ipv4.ip_forward=0 >/dev/null
    hostapd -B -P "$HOSTAPD_PID" "$HOSTAPD_CONF"
    dnsmasq --conf-file="$DNSMASQ_CONF"
    touch "$AP_ACTIVE"
    log "Isoleret AP aktiv: SSID=$ssid, management=https://$AP_ADDR:8443"
}

stop() {
    [[ -f "$AP_ACTIVE" ]] || exit 0
    [[ -f "$DNSMASQ_PID" ]] && kill "$(cat "$DNSMASQ_PID")" 2>/dev/null || true
    [[ -f "$HOSTAPD_PID" ]] && kill "$(cat "$HOSTAPD_PID")" 2>/dev/null || true
    flush_firewall
    ip addr flush dev "$AP_IF" 2>/dev/null || true
    ip link set "$AP_IF" down 2>/dev/null || true
    rm -rf "$AP_DIR"
}

case "${1:-start}" in
    start) start ;;
    stop) stop ;;
    status) hostapd_cli -i "$AP_IF" status 2>/dev/null || true ;;
    *) echo "Usage: $0 {start|stop|status}" >&2; exit 2 ;;
esac
