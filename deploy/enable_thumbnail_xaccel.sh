#!/usr/bin/env bash
# ===========================================================================
# TimeLapse Pro — aktivér thumbnail/billede X-Accel-Redirect (Lag 2)
# ---------------------------------------------------------------------------
# Lader nginx selv sende thumbnail-/billed-filer (X-Accel-Redirect) i stedet
# for at streame dem gennem uvicorn → fjerner 503-loftet på tætte gallerier.
# Python-siden er allerede bygget og flag-gated (default FRA); dette script
# tilføjer nginx-blokken + env-flag og genstarter — SIKKERT og REVERSIBELT:
#   • tager timestampede backups af både nginx-konfig og LaunchAgent-plist
#   • indsætter kun nginx-blokken hvis den mangler, FØR `location /api`
#   • kører `nginx -t` og RULLER TILBAGE automatisk hvis konfig'en er ugyldig
#   • sætter env via PlistBuddy (idempotent)
#
# Kør PÅ MAC'EN (kræver adgang til nginx-konfig + plist). Fortryd: gendan
# *.bak-<timestamp>-filerne og fjern TIMELAPSE_THUMBNAIL_XACCEL fra plist'en.
#
# Brug:
#   bash deploy/enable_thumbnail_xaccel.sh            # anvend
#   DRY_RUN=1 bash deploy/enable_thumbnail_xaccel.sh  # vis kun hvad der ville ske
# ===========================================================================
set -euo pipefail

ROOT="${TIMELAPSE_XACCEL_ROOT:-/Volumes/data-fast/timelapse-incoming/canonical-images}"
PREFIX="${TIMELAPSE_XACCEL_PREFIX:-/_protected_media}"
PLIST="${PLIST:-$HOME/Library/LaunchAgents/dk.froekjaer.timelapse-headend.plist}"
DRY_RUN="${DRY_RUN:-0}"
TS="$(date +%Y%m%d-%H%M%S)"
PB=/usr/libexec/PlistBuddy

say() { printf '  %s\n' "$*"; }
run() { if [ "$DRY_RUN" = "1" ]; then printf '  [dry-run] %s\n' "$*"; else eval "$@"; fi; }

echo "== Thumbnail X-Accel aktivering =="
say "ROOT   = $ROOT"
say "PREFIX = $PREFIX"
say "PLIST  = $PLIST"
[ "$DRY_RUN" = "1" ] && say "(DRY-RUN — intet ændres)"

# 0) Sanity
[ -d "$ROOT" ] || { echo "  ✗ ROOT findes ikke: $ROOT"; exit 1; }
[ -f "$PLIST" ] || { echo "  ✗ plist findes ikke: $PLIST"; exit 1; }

# 1) Find nginx + hovedkonfig
NGINX_BIN="$(command -v nginx || echo /opt/homebrew/bin/nginx)"
[ -x "$NGINX_BIN" ] || { echo "  ✗ nginx ikke fundet ($NGINX_BIN)"; exit 1; }
MAIN_CONF="$("$NGINX_BIN" -t 2>&1 | sed -n 's/.*configuration file \(.*\) test.*/\1/p' | head -1 || true)"
[ -z "$MAIN_CONF" ] && MAIN_CONF=/opt/homebrew/etc/nginx/nginx.conf
CONF_DIR="$(dirname "$MAIN_CONF")"
say "nginx  = $NGINX_BIN"
say "konfig = $MAIN_CONF"

# 2) Find den fil der indeholder server-blokken med 'location /api'.
#    VIGTIGT: foretræk hovedkonfig, og ekskludér backup-/temp-filer (*.bak-*, *.new)
#    så vi ALDRIG redigerer en backup ved en fejl.
if grep -qE 'location[[:space:]]+/api' "$MAIN_CONF" 2>/dev/null; then
  TARGET_CONF="$MAIN_CONF"
else
  TARGET_CONF="$(grep -rlE 'location[[:space:]]+/api' "$CONF_DIR" --include='*.conf' 2>/dev/null \
                 | grep -vE '\.(bak|new)' | head -1 || true)"
  [ -z "$TARGET_CONF" ] && TARGET_CONF="$MAIN_CONF"
fi
say "server-blok i: $TARGET_CONF"

# 3) Indsæt manglende nginx-blokke FØR den generelle 'location /api/ {'.
#    Én backup dækker begge indsættelser; nginx -t (trin 4) ruller tilbage ved fejl.
[ "$DRY_RUN" != "1" ] && cp "$TARGET_CONF" "$TARGET_CONF.bak-$TS"

# Hjælper: indsæt $2 (blok-tekst) lige før 'location /api/ {'. Matcher KUN den
# generelle /api/-location (ikke regex-locations som /api/auth/login eller de nye).
insert_before_api() {
  local label="$1" block="$2" bf
  bf="$(mktemp)"; printf '%s\n' "$block" > "$bf"
  if [ "$DRY_RUN" = "1" ]; then
    say "[dry-run] ville indsætte $label før 'location /api/ {':"
    printf '%s\n' "$block"; rm -f "$bf"; return 0
  fi
  if awk -v bf="$bf" '
        !ins && $0 ~ /location[[:space:]]+\/api\/[[:space:]]*\{/ {
          while ((getline line < bf) > 0) print line
          close(bf); ins=1
        }
        { print }
        END { if (!ins) exit 3 }
      ' "$TARGET_CONF" > "$TARGET_CONF.new"; then
    rm -f "$bf"; mv "$TARGET_CONF.new" "$TARGET_CONF"; say "+ indsat: $label"
  else
    rm -f "$bf" "$TARGET_CONF.new"
    echo "  ✗ Fandt ikke 'location /api/ {' — indsæt blokkene manuelt (se notat §5.2b)."
    [ -f "$TARGET_CONF.bak-$TS" ] && mv "$TARGET_CONF.bak-$TS" "$TARGET_CONF"
    exit 1
  fi
}

# 3a) X-Accel intern location
if grep -q "${PREFIX#/}" "$TARGET_CONF" 2>/dev/null && grep -q 'internal;' "$TARGET_CONF" 2>/dev/null; then
  say "✓ X-Accel intern location findes allerede"
else
  read -r -d '' XBLOCK <<EOF || true

    # X-Accel: intern location — nginx sender thumbnail/billede-filer direkte
    # (kun via X-Accel-Redirect efter Python-auth; ikke tilgængelig udefra).
    location ${PREFIX}/ {
        internal;
        alias ${ROOT}/;
        add_header Cache-Control "public, max-age=604800, immutable";
    }
EOF
  insert_before_api "X-Accel intern location ${PREFIX}/" "$XBLOCK"
fi

# 3b) Rate-limit-fri proxy-locations for thumbnails + billeder (DET er rate-fixet)
if grep -qE 'location[^#]*/api/thumbnails' "$TARGET_CONF" 2>/dev/null; then
  say "✓ rate-limit-fri /api/thumbnails-location findes allerede"
else
  read -r -d '' PBLOCK <<EOF || true

    # Thumbnails + billeder: auth-beskyttet, read-only media → UNDTAGET rate-limit
    # (data-API'et beholder sin limit_req; kun media slipper fri). ^~ vinder over
    # regex-locations og arver derfor IKKE limit_req fra 'location /api/'.
    location ^~ /api/thumbnails/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_pass_header Set-Cookie;
    }
    location ^~ /api/images/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_pass_header Set-Cookie;
    }
EOF
  insert_before_api "rate-limit-fri /api/thumbnails/ + /api/images/" "$PBLOCK"
fi

# 4) Valider nginx; rul tilbage ved fejl
if [ "$DRY_RUN" != "1" ]; then
  if ! "$NGINX_BIN" -t; then
    echo "  ✗ nginx -t FEJLEDE — ruller tilbage"
    [ -f "$TARGET_CONF.bak-$TS" ] && mv "$TARGET_CONF.bak-$TS" "$TARGET_CONF"
    exit 1
  fi
  say "✓ nginx -t ok"
fi

# 5) env i plist (idempotent)
set_env() {
  if [ "$DRY_RUN" = "1" ]; then say "[dry-run] env $1=$2"; return; fi
  "$PB" -c "Set :EnvironmentVariables:$1 $2" "$PLIST" 2>/dev/null || \
  "$PB" -c "Add :EnvironmentVariables:$1 string $2" "$PLIST"
}
if [ "$DRY_RUN" != "1" ]; then
  cp "$PLIST" "$PLIST.bak-$TS"
  "$PB" -c "Add :EnvironmentVariables dict" "$PLIST" 2>/dev/null || true
fi
set_env TIMELAPSE_THUMBNAIL_XACCEL on
set_env TIMELAPSE_XACCEL_ROOT "$ROOT"
set_env TIMELAPSE_XACCEL_PREFIX "$PREFIX"
[ "$DRY_RUN" != "1" ] && say "+ env sat i plist (backup: $PLIST.bak-$TS)"

# 6) Reload nginx + genstart headend
run "\"$NGINX_BIN\" -s reload"
run "launchctl kickstart -k gui/$(id -u)/dk.froekjaer.timelapse-headend"
if [ "$DRY_RUN" != "1" ]; then
  sleep 25
  echo "== Verifikation =="
  curl -s -o /dev/null -w "  health: %{http_code}\n" http://127.0.0.1:8000/api/health || true
  say "Load Frøkjær-galleri (Cmd+Shift+R). Et thumbnail-svar bør nu komme fra nginx;"
  say "bekræft fx i Network-fanen at der IKKE længere kommer 503 under scroll."
fi
echo "== Færdig =="
