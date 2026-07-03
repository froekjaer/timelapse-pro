#!/bin/zsh
set -euo pipefail

ENV_FILE="${TIMELAPSE_WIFI_ENV_FILE:-/etc/timelapse/wifi.env}"
IFACE="${TIMELAPSE_WIFI_INTERFACE:-en1}"
SSID="${TIMELAPSE_WIFI_SSID:-p-froekjaer}"
ROUTER="${TIMELAPSE_WIFI_ROUTER:-192.168.86.1}"
LOG_PREFIX="[timelapse-wifi-ensure]"

export PATH="/usr/sbin:/usr/bin:/bin:/sbin"

if [[ -r "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

log() {
  echo "$LOG_PREFIX $*"
}

wifi_power() {
  /usr/sbin/networksetup -getairportpower "$IFACE" 2>/dev/null || true
}

has_ip() {
  /usr/sbin/ipconfig getifaddr "$IFACE" >/dev/null 2>&1
}

router_reachable() {
  /sbin/ping -q -c 1 -W 1000 "$ROUTER" >/dev/null 2>&1
}

ensure_power() {
  if ! wifi_power | /usr/bin/grep -q "On"; then
    log "WiFi power is off on $IFACE, enabling"
    /usr/sbin/networksetup -setairportpower "$IFACE" on || true
    sleep 5
  fi
}

join_saved_network() {
  log "joining saved WiFi network '$SSID' on $IFACE"
  /usr/sbin/networksetup -setairportnetwork "$IFACE" "$SSID" || true
  sleep 8
}

renew_address() {
  log "renewing address on $IFACE"
  /usr/sbin/ipconfig set "$IFACE" DHCP || true
  sleep 5
}

cycle_wifi() {
  log "cycling WiFi power on $IFACE"
  /usr/sbin/networksetup -setairportpower "$IFACE" off || true
  sleep 5
  /usr/sbin/networksetup -setairportpower "$IFACE" on || true
  sleep 8
}

ensure_power

if has_ip && router_reachable; then
  log "ok: $IFACE has IP and router $ROUTER is reachable"
  exit 0
fi

join_saved_network
renew_address

if has_ip && router_reachable; then
  log "recovered after join/renew"
  exit 0
fi

cycle_wifi
join_saved_network
renew_address

if has_ip && router_reachable; then
  log "recovered after WiFi power cycle"
  exit 0
fi

log "warning: WiFi still not healthy after recovery attempts"
exit 1
