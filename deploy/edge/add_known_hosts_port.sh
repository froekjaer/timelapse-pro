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
# @revoked / @cert-authority entries are reported by ssh-keygen -F only on the
# "# Host ... found: line N <MARKER>" comment line. Refuse to reason about
# fingerprints for a host:port that carries any marker.
marker_check() {
  local m; m="$(ssh-keygen -F "[$1]:$2" -f "$KH" 2>/dev/null | grep -E '^# Host .* found: line [0-9]+ [A-Z]' || true)"
  if [ -n "$m" ]; then
    echo "FEJL: [$1]:$2 har en markeret known_hosts-linje (fx @revoked/@cert-authority) i $KH: $m — håndtér manuelt." >&2; exit 2
  fi
}
marker_check "$PINNED_HOST" "$OLD"
marker_check "$HOST" "$NEW"

old_fps="$(fp_pinned "$PINNED_HOST" "$OLD")"
if [ -z "$old_fps" ]; then
  echo "FEJL: ingen pinned nøgle for [$PINNED_HOST]:$OLD i $KH — afbryder (ingen TOFU)." >&2; exit 1
fi
existing="$(fp_pinned "$HOST" "$NEW")"
if [ -n "$existing" ]; then
  # Presence is not proof: every key already pinned for the new port must be
  # one of the keys pinned for the old port, or the cutover would break.
  bad="$(grep -vxF -f <(printf '%s\n' "$old_fps") <<<"$existing" || true)"
  if [ -n "$bad" ]; then
    echo "FEJL: [$HOST]:$NEW findes allerede i $KH med en nøgle, der IKKE matcher [$PINNED_HOST]:$OLD: $bad — ret/fjern linjen manuelt." >&2; exit 2
  fi
fi

# Always check what the new port serves right now — also when an entry
# already exists (rotated key, wrong NAT target, other service).
# Private scratch directory (0700): no predictable sibling files in /tmp
# that another local user could pre-create as symlinks while we run as root.
scratch="$(mktemp -d)"; trap 'rm -rf "$scratch"' EXIT
tmp="$scratch/scan"; one="$scratch/one"
ssh-keyscan -p "$NEW" -T 10 "$HOST" 2>/dev/null > "$tmp" || true
[ -s "$tmp" ] || { echo "FEJL: ingen svar fra $HOST:$NEW (lytter Headend/NAT?)" >&2; exit 1; }

live_ok=()
while read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  printf '%s\n' "$line" > "$one"
  fp="$(ssh-keygen -l -f "$one" 2>/dev/null | grep -o 'SHA256:[^ ]*' || true)"
  if [ -n "$fp" ] && grep -qxF "$fp" <<<"$old_fps"; then
    live_ok+=("$fp	$line")
  fi
done < "$tmp"
[ "${#live_ok[@]}" -gt 0 ] || { echo "FEJL: nøglen på $HOST:$NEW matcher IKKE den pinned nøgle for [$PINNED_HOST]:$OLD — intet tilføjet." >&2; exit 2; }

if [ -n "$existing" ]; then
  # Existing entries must cover a key the port actually serves now.
  for item in "${live_ok[@]}"; do
    if grep -qxF "${item%%	*}" <<<"$existing"; then
      echo "OK: [$HOST]:$NEW findes allerede i $KH, matcher [$PINNED_HOST]:$OLD og serveres live nu:"; printf '%s\n' "$existing"; exit 0
    fi
  done
  echo "FEJL: [$HOST]:$NEW i $KH matcher ingen nøgle, som porten serverer nu — ret/fjern linjen manuelt." >&2; exit 2
fi

for item in "${live_ok[@]}"; do
  printf '%s\n' "${item#*	}" >> "$KH"
  echo "TILFØJET [$HOST]:$NEW  ${item%%	*}"
done
