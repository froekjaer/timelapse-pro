#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — End-to-end update flow test
# Kør fra Mac Mini headend: bash headend/tools/test_update_flow.sh
#
# Tester hele flowet:
#   1. Edge inventory → CMDB
#   2. CMDB → PendingUpdate
#   3. Headend artifact (catalog-current)
#   4. Update policy leveres til edge
#   5. Edge poller og downloader
#
# Kræver: jq, curl, HEADEND_URL, HEADEND_TOKEN (admin JWT)
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

HEADEND_URL="${HEADEND_URL:-https://timelapse-api.froekjaer.dk:10443/api}"
DEVICE_ID="${DEVICE_ID:-TL-C87FF9587CA0}"

# Auth token — sæt via env eller prompt
if [[ -z "${HEADEND_TOKEN:-}" ]]; then
    echo "HEADEND_TOKEN ikke sat. Hent det fra browseren (DevTools → Application → Cookies → tl_session)"
    echo "Eksempel: export HEADEND_TOKEN=eyJhbGciOi..."
    exit 1
fi

H="Authorization: Bearer $HEADEND_TOKEN"
CT="Content-Type: application/json"

ok()  { echo "  ✓ $*"; }
err() { echo "  ✗ $*" >&2; }
sep() { echo; echo "── $* ──────────────────────────────────────"; }

# ── 1. Tjek headend er tilgængeligt ──────────────────────────────────────────
sep "1. Headend health check"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEADEND_URL/health" || echo "000")
if [[ "$STATUS" == "200" ]]; then
    ok "Headend svarer ($HEADEND_URL)"
else
    err "Headend utilgængeligt (HTTP $STATUS) — tjek VPN/tunnel"
    exit 1
fi

# ── 2. CMDB status for edgen ─────────────────────────────────────────────────
sep "2. CMDB status for $DEVICE_ID"
CMDB=$(curl -sf -H "$H" "$HEADEND_URL/cmdb/$DEVICE_ID" 2>/dev/null || echo "{}")
INV_AT=$(echo "$CMDB" | jq -r '.inventory_reported_at // "aldrig"')
HW=$(echo "$CMDB" | jq -r '.hardware_model // "ukendt"')
APP=$(echo "$CMDB" | jq -r '.app_version // "ukendt"')
echo "  Hardware:  $HW"
echo "  App:       $APP"
echo "  Seneste inventory: $INV_AT"

# ── 3. Manuelle inventory rapport (simulér edge restart) ──────────────────────
sep "3. Trigger inventory-rapport fra edge (via SSH)"
echo "  Kør på edge (ssh -p 2201 orangepi@localhost):"
echo ""
echo "    sudo systemctl restart timelapse-edge"
echo "    # Venter 30 sek, derefter:"
echo "    sudo journalctl -u timelapse-edge -n 50 --no-pager | grep -i 'inventar\|inventory\|CMDB'"
echo ""
echo "  Eller kør inventory manuelt:"
echo "    cd /opt/timelapse && sudo python3 -c \""
echo "    import sys; sys.path.insert(0,'edge')"
echo "    from edge.utils.inventory import collect_inventory"
echo "    import json; print(json.dumps(collect_inventory({}), indent=2, default=str))"
echo "    \" | head -80"

# ── 4. PendingUpdates for device ─────────────────────────────────────────────
sep "4. Aktuelle PendingUpdates for $DEVICE_ID"
UPDATES=$(curl -sf -H "$H" "$HEADEND_URL/updates/pending?scope_id=$DEVICE_ID" 2>/dev/null || echo "[]")
echo "$UPDATES" | jq -r '.[] | "  [\(.status)] \(.update_type) v\(.version // "?") — \(.severity // "?")"' 2>/dev/null || \
    echo "  (ingen updates eller jq fejl)"

# ── 5. Byg/registrer artifact for nuværende kode ─────────────────────────────
sep "5. Registrer artifact for nuværende git HEAD"
ART=$(curl -sf -X POST -H "$H" -H "$CT" \
    "$HEADEND_URL/updates/artifacts/catalog-current" 2>/dev/null || echo "{}")
ART_ID=$(echo "$ART" | jq -r '.artifact_id // "fejl"')
if [[ "$ART_ID" != "fejl" && "$ART_ID" != "null" ]]; then
    ok "Artifact registreret: $ART_ID"
else
    err "Artifact fejlede: $(echo "$ART" | jq -c .)"
fi

# ── 6. Opret test timelapse_updates PendingUpdate (lab) ──────────────────────
sep "6. Opret test PendingUpdate (timelapse_updates, lab)"
echo "  Kør i psql på headend:"
echo ""
cat << 'PSQL'
  psql timelapse_db -c "
  INSERT INTO pending_updates
    (update_type, version, description, severity, scope, scope_id,
     status, environment, target_device_ids, created_at)
  VALUES
    ('timelapse_updates',
     'lab-test-$(date +%Y%m%d)',
     'Lab end-to-end test opdatering',
     'low',
     'device',
     'TL-C87FF9587CA0',
     'pending',
     'test',
     '[\"TL-C87FF9587CA0\"]',
     NOW())
  RETURNING id, update_type, status;
  "
PSQL
echo ""
echo "  Bind artifact til update (erstat UPDATE_ID og ARTIFACT_ID):"
echo "    curl -X POST -H 'Authorization: Bearer \$TOKEN' -H 'Content-Type: application/json' \\"
echo "      -d '{\"artifact_id\":\"$ART_ID\"}' \\"
echo "      '$HEADEND_URL/updates/UPDATE_ID/bind-artifact'"
echo ""
echo "  Godkend update:"
echo "    curl -X POST -H 'Authorization: Bearer \$TOKEN' -H 'Content-Type: application/json' \\"
echo "      -d '{\"reason\":\"lab test\"}' \\"
echo "      '$HEADEND_URL/updates/UPDATE_ID/approve'"

# ── 7. Test update policy endpoint (som edge ser det) ────────────────────────
sep "7. Update policy som edge ser den"
POLICY=$(curl -sf -H "$H" "$HEADEND_URL/updates/policy/$DEVICE_ID" 2>/dev/null || echo "{}")
PENDING=$(echo "$POLICY" | jq -r '.pending_updates | length' 2>/dev/null || echo "?")
echo "  Godkendte opdateringer til edge: $PENDING"
echo "$POLICY" | jq -r '.pending_updates[]? | "    [\(.status)] \(.update_type) id=\(.id)"' 2>/dev/null || true

# ── 8. SSH-kommandoer til edge-test ──────────────────────────────────────────
sep "8. Edge test-kommandoer (via: ssh -p 2201 orangepi@localhost)"
cat << 'SSH'
  # Se agent logs live:
  sudo journalctl -u timelapse-edge -f

  # Tjek update check manuelt (TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE=1 for lab):
  sudo TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE=1 TIMELAPSE_ENV=lab \
    systemctl restart timelapse-edge

  # Bekræft git version:
  git -C /opt/timelapse rev-parse --short HEAD

  # Tjek inventory samles korrekt:
  cd /opt/timelapse
  sudo python3 -c "
  import sys; sys.path.insert(0, 'edge')
  from edge.utils.inventory import collect_inventory
  import json
  inv = collect_inventory({'storage': {'base_dir': '/data'}})
  print('Hardware:', inv['hardware_model'], '/', inv['soc_model'])
  print('OS:', inv['os_name'])
  print('App:', inv['app_version'], 'git:', inv.get('git_commit'))
  print('Users:', [u['username'] for u in inv.get('local_users',[])])
  print('Services:', len(inv.get('services',[])), 'registreret')
  print('OS updates:', inv.get('os_updates_available',{}).get('total',0), 'tilgaengelige')
  "

  # Tjek update policy manuelt:
  TOKEN=$(cat /run/timelapse/api_token 2>/dev/null || cat /etc/timelapse/bootstrap.yaml | grep api_token | awk '{print $2}')
  DEVICE=$(cat /etc/timelapse/bootstrap.yaml | grep device_id | awk '{print $2}')
  curl -sf -H "Authorization: Bearer $TOKEN" \
    https://timelapse-api.froekjaer.dk:10443/api/updates/policy/$DEVICE | python3 -m json.tool

SSH

sep "Færdig"
echo "  Genstart timelapse-edge på edge for at trigge inventory + update check:"
echo "    ssh -p 2201 orangepi@localhost 'sudo systemctl restart timelapse-edge'"
