# TimeLapse Pro — CMDB & Opdaterings-pipeline

Komplet implementering af hele opdateringsflowet for **alle** opdateringstyper
(OS Sikkerhed, OS Opdatering, App Sikkerhed, App Opdatering, TimeLapse) på
**begge** platforme (Headend + Edge).

Dette løser samtidig siden der hang på **"Henter Edge flow-status…"** — den
manglede backend-endpointet `/api/cmdb/edge-flow`, som nu findes.

## Hvad flowet gør (ende-til-ende)

1. **CMDB indsamler** installeret OS/software/patches fra Headend (brew/pip/git)
   og Edge (apt/pip/git, sendt i heartbeat).
2. **Opdager opdateringer** (brew/pip/apt outdated) og udleder kritikalitet.
3. **Genererer SBOM** i CycloneDX 1.5 pr. platform.
4. **Viser inventory** med installeret + tilgængelig version, farvet efter kritikalitet.
5. **Pakketerer** opdateringer pr. (platform, kategori) — security/functional + TimeLapse.
6. **Frigiv til test** → kun test-enheder får pakken.
7. **Aftest efter testplanen** → **Frigiv til staging og/eller produktion** (med gate-kontrol).
8. **Auto-deploy** til relevante enheder afhængigt af auto-accept-policy
   pr. kunde/site/kamera for hver kategori.
9. **Kunde-accept** når auto er slået fra: change request via **mail** og/eller
   **ticket-webhook** (API-integration), med godkend/afvis-links.

## Filer

### Headend (Python)
- `headend/cmdb_models.py` — datamodel (6 tabeller)
- `headend/cmdb/scanner.py` — indsamling + kritikalitet + edge-ingest
- `headend/cmdb/sbom.py` — CycloneDX SBOM
- `headend/cmdb/pipeline.py` — pakketering, promovering, policy, change requests
- `headend/cmdb/notify.py` — mail + ticket-webhook
- `headend/cmdb/routes.py` — alle `/api/cmdb/*` endpoints (inkl. `/edge-flow`)

### Edge (Python)
- `edge/cmdb/collector.py` — Ubuntu/apt/pip/git inventory (cachet)
- `edge/cmdb/executor.py` — retired fail-safe stub; Edge-opdateringer udføres kun af `EdgeAgent` via Headend-signerede artifacts.
- `edge/agent_cmdb_integration.py` — klip-ind metoder til `agent.py`

### UI (React/TypeScript)
- `timelapse-ui/src/pages/UpdatesPage.tsx` — CMDB, pipeline, SBOM, change requests
- `timelapse-ui/src/pages/EdgeFlowPage.tsx` — flow-overblik pr. enhed (fikser den hængende side)

### Installation
- `install_cmdb.sh` — kopierer moduler, wirer router + heartbeat ind i `main.py`
- `install_ui.sh` — kopierer sider, wirer routes + navbar
- `docs/Testplan_CMDB_Opdaterings-pipeline.md` — fuld testplan

## Installation (på Mac Mini headend)

```bash
# 1) Backend
bash install_cmdb.sh ~/projects/timelapse-pro

# 2) UI
bash install_ui.sh ~/projects/timelapse-pro
cd ~/projects/timelapse-pro/timelapse-ui && npm run build

# 3) Genstart headend
sudo launchctl unload /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist
sudo launchctl load   /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist

# 4) Første scan
curl -X POST https://timelapse-api.froekjaer.dk:10443/api/cmdb/scan

# 5) Distribuér edge-koden (pipelinen tager resten)
cd ~/projects/timelapse-pro
git add edge/cmdb edge/agent_cmdb_integration.py && git commit -S -m "CMDB edge" && git push
```

## Edge-integration (agent.py)

Tilføj til `EdgeAgent` (se `edge/agent_cmdb_integration.py` for fuld kode):
- `_collect_cmdb_inventory()` — embed i heartbeat
- `_process_cmdb_updates()` — kald i run-loop efter heartbeat
- Udvid `headend_client.send_heartbeat(...)` med `cmdb_inventory` parameter

## Auto-accept policy (config)

Sæt under `updates` i kunde/site/enheds-config (senere lag vinder):

```json
{"updates": {
  "os_security": true,
  "os_update": false,
  "app_security": true,
  "app_update": false,
  "timelapse": true
}}
```

## Ticket-integration (kundens system)

Sæt i kundens `config_overrides`:
```json
{"integrations": {"ticket_webhook_url": "https://kunde.example/api/tickets"}}
```
Headend POST'er en generisk JSON-payload med `approve_url`/`reject_url`/`token`.
Svarer kundens system med `{"ticket_id": "..."}`, gemmes det som reference.
