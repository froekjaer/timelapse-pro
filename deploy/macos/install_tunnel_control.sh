#!/bin/zsh
set -euo pipefail

usage() {
  echo "Brug: sudo $0 --service-user USER --tunnel-user USER [--source PATH]" >&2
  exit 2
}

SERVICE_USER=""
TUNNEL_USER=""
SOURCE="$(cd "$(dirname "$0")" && pwd)/timelapse_tunnel_control.py"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --service-user) SERVICE_USER="$2"; shift 2 ;;
    --tunnel-user) TUNNEL_USER="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ "$(id -u)" == "0" ]] || { echo "Skal køres som root" >&2; exit 1; }
print -r -- "$SERVICE_USER" | grep -Eq '^_?[A-Za-z][A-Za-z0-9_-]{0,30}$' || usage
print -r -- "$TUNNEL_USER" | grep -Eq '^_?[A-Za-z][A-Za-z0-9_-]{0,30}$' || usage
id "$SERVICE_USER" >/dev/null 2>&1 || { echo "Ukendt servicebruger: $SERVICE_USER" >&2; exit 1; }
id "$TUNNEL_USER" >/dev/null 2>&1 || { echo "Ukendt tunnelbruger: $TUNNEL_USER" >&2; exit 1; }
[[ -f "$SOURCE" ]] || { echo "Helper mangler: $SOURCE" >&2; exit 1; }

HELPER="/usr/local/libexec/timelapse-tunnel-control"
CONFIG="/etc/timelapse/tunnel-control.conf"
SUDOERS="/etc/sudoers.d/timelapse-tunnel-control"
mkdir -p /usr/local/libexec /etc/timelapse /etc/sudoers.d
install -o root -g wheel -m 0755 "$SOURCE" "$HELPER"
printf '%s\n' "$TUNNEL_USER" > "$CONFIG"
chown root:wheel "$CONFIG"
chmod 0644 "$CONFIG"
printf '%s ALL=(root) NOPASSWD: %s close *\n' "$SERVICE_USER" "$HELPER" > "$SUDOERS"
chmod 0440 "$SUDOERS"
visudo -cf "$SUDOERS" >/dev/null
echo "Tunnel-control installeret for service=$SERVICE_USER tunnel=$TUNNEL_USER"
