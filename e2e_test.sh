#!/usr/bin/env bash
# TimeLapse Pro — Deploy + End-to-end test
# Kør fra Mac Mini: bash e2e_test.sh
# ─────────────────────────────────────────
set -euo pipefail

EDGE_SSH="ssh -p 2201 -o StrictHostKeyChecking=no orangepi@localhost"
EDGE_PASS="orangepi"
PROJECT="/Users/peter/projects/timelapse-pro"
HEADEND_URL="https://timelapse-api.froekjaer.dk:10443/api"

ok()  { echo "  ✓ $*"; }
err() { echo "  ✗ $*"; }
sep() { echo; echo "══ $* ══════════════════════════════════════════"; }

# ── Hjælpefunktion: kør sudo-kommando på edge ─────────────────────────────
edge() {
    $EDGE_SSH "echo '$EDGE_PASS' | sudo -S $*" 2>/dev/null
}

# ── 1. SSH-forbindelse til edge ────────────────────────────────────────────
sep "1. SSH til edge"
if $EDGE_SSH "echo ok" &>/dev/null; then
    ok "SSH forbundet til edge"
else
    err "Kan ikke forbinde til edge på localhost:2201"
    exit 1
fi

# ── 2. Synk kode til edge ─────────────────────────────────────────────────
sep "2. Git pull på edge"
edge "git -C /opt/timelapse pull --ff-only 2>&1" && ok "git pull ok" || {
    echo "  Prøver med stash..."
    edge "git -C /opt/timelapse stash && git -C /opt/timelapse pull --ff-only 2>&1"
}
EDGE_COMMIT=$(edge "git -C /opt/timelapse rev-parse --short HEAD 2>/dev/null")
echo "  Edge commit: $EDGE_COMMIT"

# ── 3. Test inventory lokalt på edge ──────────────────────────────────────
sep "3. Inventory-test på edge"
INV_OUT=$($EDGE_SSH "cd /opt/timelapse && echo '$EDGE_PASS' | sudo -S python3 -c \"
import sys, json
sys.path.insert(0, 'edge')
from edge.utils.inventory import collect_inventory
inv = collect_inventory({'storage': {'base_dir': '/data'}})
print('MODEL:', inv.get('hardware_model','?'))
print('OS:', inv.get('os_name','?'))
print('APP:', inv.get('app_version','?'), 'git:', inv.get('git_commit','?'))
print('USERS:', [u['username'] for u in inv.get('local_users',[])])
print('SERVICES:', len(inv.get('services',[])))
print('OS_UPDATES:', inv.get('os_updates_available',{}).get('total',0), 'total,', inv.get('os_updates_available',{}).get('security',0), 'security')
\" 2>/dev/null")
echo "$INV_OUT" | sed 's/^/  /'

# ── 4. Genstart edge agent ─────────────────────────────────────────────────
sep "4. Genstart timelapse-edge"
edge "systemctl restart timelapse-edge" && ok "Genstartet" || err "Genstart fejlede"
sleep 5

# ── 5. Tjek edge logs ─────────────────────────────────────────────────────
sep "5. Edge agent logs (seneste 30 linjer)"
$EDGE_SSH "echo '$EDGE_PASS' | sudo -S journalctl -u timelapse-edge -n 30 --no-pager 2>/dev/null" | \
    grep -E "inventory|CMDB|heartbeat|update|NTP|ERROR|WARNING" | sed 's/^/  /' || \
    $EDGE_SSH "echo '$EDGE_PASS' | sudo -S journalctl -u timelapse-edge -n 20 --no-pager 2>/dev/null" | tail -20 | sed 's/^/  /'

# ── 6. Hent HEADEND_TOKEN ─────────────────────────────────────────────────
sep "6. Headend API test"
# Prøv at hente token fra edge's konfiguration
EDGE_TOKEN=$($EDGE_SSH "cat /etc/timelapse/bootstrap.yaml 2>/dev/null | grep -A1 'api_token' | tail -1 | tr -d ' ' || cat /run/timelapse/api_token 2>/dev/null || echo ''" 2>/dev/null || echo "")
DEVICE_ID=$($EDGE_SSH "cat /etc/timelapse/bootstrap.yaml 2>/dev/null | grep 'device_id' | awk '{print \$2}' | tr -d \"'\" || echo 'TL-C87FF9587CA0'" 2>/dev/null || echo "TL-C87FF9587CA0")
echo "  Device ID: $DEVICE_ID"

if [[ -n "$EDGE_TOKEN" && "$EDGE_TOKEN" != "" ]]; then
    ok "Token fundet"

    # CMDB status
    CMDB=$(curl -sk -H "Authorization: Bearer $EDGE_TOKEN" "$HEADEND_URL/cmdb/$DEVICE_ID" 2>/dev/null || echo "{}")
    INV_AT=$(echo "$CMDB" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('inventory_reported_at','aldrig'))" 2>/dev/null || echo "?")
    echo "  Seneste CMDB inventory: $INV_AT"

    # Pending updates
    PENDING=$(curl -sk -H "Authorization: Bearer $EDGE_TOKEN" "$HEADEND_URL/updates/policy/$DEVICE_ID" 2>/dev/null || echo "{}")
    N=$(echo "$PENDING" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('pending_updates',[])))" 2>/dev/null || echo "?")
    echo "  Godkendte opdateringer til edge: $N"
else
    echo "  (ingen token — tjek CMDB manuelt i UI'en)"
fi

sep "Færdig"
echo "  Kig i UI'en under CMDB for $DEVICE_ID for at se inventory-data"
