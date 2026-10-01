#!/usr/bin/env bash
# Add a pinned known_hosts entry for HOST:NEW_PORT on an Edge, but only if the
# host key served on NEW_PORT is identical to the one already pinned for
# HOST:OLD_PORT. No trust-on-first-use. Used for the 2026-10 port move
# (SFTP 22222 -> 9022, reverse-SSH 22022 -> 9222); see
# Dokumentation/PORT_OMLAEGNING_9022_9222_2026-10-01.md.
#
# Usage: sudo add_known_hosts_port.sh HOST OLD_PORT NEW_PORT [KNOWN_HOSTS] [PINNED_HOST]
#   PINNED_HOST: host name the key is currently pinned under, if it differs
#   from HOST (e.g. SFTP moving from timelapse.froekjaer.dk:22222 to
#   backend.timelapse-pro.dk:9022). Defaults to HOST.
set -euo pipefail

HOST="${1:?host}"; OLD="${2:?old port}"; NEW="${3:?new port}"
KH="${4:-/opt/timelapse/edge/ssh/known_hosts}"
PINNED_HOST="${5:-$HOST}"

fp_pinned() { ssh-keygen -l -F "[$1]:$2" -f "$KH" 2>/dev/null | grep -v '^#' | grep -o 'SHA256:[^ ]*' | sort -u || true; }

old_fps="$(fp_pinned "$PINNED_HOST" "$OLD")"
if [ -z "$old_fps" ]; then
  echo "FEJL: ingen pinned nøgle for [$PINNED_HOST]:$OLD i $KH — afbryder (ingen TOFU)." >&2; exit 1
fi
if [ -n "$(fp_pinned "$HOST" "$NEW")" ]; then
  echo "OK: [$HOST]:$NEW findes allerede i $KH:"; fp_pinned "$HOST" "$NEW"; exit 0
fi

tmp="$(mktemp)"; trap 'rm -f "$tmp" "$tmp.one"' EXIT
ssh-keyscan -p "$NEW" -T 10 "$HOST" 2>/dev/null > "$tmp" || true
[ -s "$tmp" ] || { echo "FEJL: ingen svar fra $HOST:$NEW (lytter Headend/NAT?)" >&2; exit 1; }

# Keep only key types whose fingerprint matches the pinned old-port key.
matched=0
while read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  printf '%s\n' "$line" > "$tmp.one"
  fp="$(ssh-keygen -l -f "$tmp.one" 2>/dev/null | grep -o 'SHA256:[^ ]*' || true)"
  if [ -n "$fp" ] && grep -qxF "$fp" <<<"$old_fps"; then
    echo "$line" >> "$KH"; matched=1
    echo "TILFØJET [$HOST]:$NEW  $fp"
  fi
done < "$tmp"

[ "$matched" = 1 ] || { echo "FEJL: nøglen på $HOST:$NEW matcher IKKE den pinned nøgle for [$PINNED_HOST]:$OLD — intet tilføjet." >&2; exit 2; }
