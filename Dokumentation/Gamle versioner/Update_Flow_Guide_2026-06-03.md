# TimeLapse Pro - Headend-drevet update flow

**Dato:** 2026-06-03  
**Status:** Arbejdsguide efter live test med `TL-C87FF9587CA0`

## Arkitekturprincip

Edge rapporterer **installed-state** til Headend/CMDB:

- hardware
- firmware/kernel
- OS packages
- Python/venv packages
- Timelapse Pro app version
- services/hardening state

Headend er **update authority**:

- sammenligner installed-state med et Headend-ejet katalog eller artifact catalog
- opretter `pending_updates`
- genererer change tickets
- kræver approval
- stiller godkendte actions/artifacts klar

Edge må kun hente/polle godkendte handlinger fra Headend. Edge skal ikke have direkte GitHub/Internet i production.

## Update-kategorier

- `os_security`
- `os_updates`
- `app_security`
- `app_updates`
- senere: `application_security` / `application_updates` for tredjepartsapplikationer

## Live test 2026-06-03

Edge:

```text
TL-C87FF9587CA0
```

CMDB installed-state findes:

- Ubuntu 24.04.4 LTS
- kernel `5.15.147-sun60iw2`
- app version `2.8.0`
- `package_manager=apt/dpkg`
- OS packages rapporteret
- software inventory rapporteret

Edge login-banner viste:

```text
49 security updates available, 87 updates total
```

Headend reconciliation dry-run matchede:

```text
49 os_security
39 os_updates
```

Der blev oprettet LAB pending updates:

```text
id=12 os_security 49 pakker high pending lab
id=11 os_updates  39 pakker low  pending lab
```

Edge policy endpoint returnerer fortsat ingen pending til Edge, fordi Edge kun må se:

```text
approved
rollback_requested
```

Det er korrekt. Pending skal behandles i Headend/UI.

## Kommandoer

### 1. Verificer CMDB installed-state

```bash
psql postgresql://timelapse@localhost/timelapse_db -c "
SELECT device_id, hostname, environment, os_name, kernel_version,
       app_version, package_manager, inventory_reported_at,
       length(os_packages) AS os_pkg_chars,
       length(venv_packages) AS venv_pkg_chars,
       length(software_inventory) AS sw_chars
FROM device_inventory
ORDER BY device_id;"
```

### 2. Importer et Headend-ejet LAB-katalog

Edge maa ikke generere listen over manglende pakker med `apt list --upgradable`.
Headend skal sammenligne CMDB installeret-state med et LAB-testet update-katalog
fra mirror/artifact pipeline.

Kataloget skal have schema `dk.froekjaer.timelapse.update-catalog.v1` og mindst
indeholde `packages[]` med `name`, `available_version`, `category`, `severity`
og `source_repo`.

### 3. Dry-run reconcile

```bash
DATABASE_URL=postgresql://timelapse@localhost/timelapse_db \
headend/venv/bin/python headend/tools/reconcile_updates.py \
  --device-id TL-C87FF9587CA0 \
  --catalog /var/lib/timelapse/update-catalogs/edge-os-lab-approved.json \
  --environment lab \
  --plan-output /var/lib/timelapse/update-plans/TL-C87FF9587CA0-lab.json \
  --dry-run
```

### 4. Opret pending updates

```bash
DATABASE_URL=postgresql://timelapse@localhost/timelapse_db \
headend/venv/bin/python headend/tools/reconcile_updates.py \
  --device-id TL-C87FF9587CA0 \
  --catalog /var/lib/timelapse/update-catalogs/edge-os-lab-approved.json \
  --environment lab \
  --plan-output /var/lib/timelapse/update-plans/TL-C87FF9587CA0-lab.json \
  --create
```

### 5. Verificer pending queue

```bash
psql postgresql://timelapse@localhost/timelapse_db -c "
SELECT id, update_type, version, severity, environment, status
FROM pending_updates
WHERE status='pending'
ORDER BY id DESC;"
```

### 6. UI change ticket

Gaa til:

```text
/change-tickets
```

Opret change ticket for pending update, fx:

```text
id=12 os_security
```

Godkend ikke production-deploy uden:

- rollback-plan
- maintenance window
- backup/restore evidence
- package list evidence
- forventet downtime/reboot-afklaring

### 7. Edge poll

Edge poller:

```text
GET /api/updates/policy/{device_id}
```

Edge får kun updates naar status er:

```text
approved
rollback_requested
```

## Kendte gaps efter testen

1. `device_inventory` mangler `device_type`, `credential_required` og tydelig dummy/import/onboarding klassifikation.
2. Gammelt endpoint `/api/updates/available` findes stadig og repræsenterer Edge-reported availability. Det bør markeres LAB-only eller udfases.
3. Heartbeat `_process_update_report()` kan stadig oprette updates ud fra `diag.updates`; det skal ikke være production path.
4. OS update execution på Edge bruger stadig `apt-get upgrade`; production kræver Headend-styret package/cache/artifact og rollback/evidence.
5. Change ticket bør gøres obligatorisk før approval af updates.
6. UI bør vise package evidence fra reconcile-kataloget, ikke kun antal pakker.
