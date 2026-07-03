# TimeLapse Pro - frisk QA og SABSA reassessment

Dato: 2026-06-22  
Scope: Mac Mini Headend, ekstern disk `/Volumes/data-fast`, aktiv Edge `TL-C87FF9587CA0`, CMDB, update-flow, backup/storage, node-agent og pre-production readiness.  
Status: Lab/pre-production. Ikke klar til egentlig production-site før nedenstående P1/P2 er lukket.

## Executive summary

Systemet er væsentligt bedre end før opstartsproblemerne: Headend kører igen stabilt fra den nye venv, public UI/API svarer, aktiv Edge tager billeder, og update-flowets app/artifact E2E-test fra 2026-06-21 er stadig gyldig.

Der var dog en ny P1 efter flytningen til ekstern disk: Headend forsøgte fortsat at skrive captures til `/Volumes/data`, mens den faktiske disk nu er `/Volumes/data-fast`. Det gav API upload `500` fra aktiv Edge. Denne konfigurationsfejl er rettet i DB for:

- `sftp_base`
- `sftp_remote_base`
- `backup_nas_path`
- site override for `Nordre Villavej 17c`

Headend er genstartet efter rettelsen, og `/api/health` svarer OK. Den nye canonical capture-sti på `/Volumes/data-fast` er verificeret skrivbar.

De vigtigste resterende punkter er:

1. Node-agent på Mac Mini er stoppet siden 2026-06-22 07:46 og er ikke loaded i launchctl, selv om plist findes.
2. Installeret node-agent-kopi i `/opt/timelapse-node-agent` er root-ejet og bruger stadig gammel `/Volumes/data`-logik.
3. Update #33 er approved til stale/sekundær Edge `TL-DCA63234D813`, ikke til aktiv Edge `TL-C87FF9587CA0`.
4. CMDB viser stadig stale Edge-status som online i `devices.status`; UI/GRC bør bruge freshness-baseret status.
5. Secrets ligger fortsat i DB/LaunchAgent-miljø som runtime secrets. Det fungerer, men er ikke en moden Keychain/secret-management model.
6. Kamera-drift har stadig config drift på Nikon Z30: focus, ISO og white balance.

## Evidens 2026-06-22

### Headend process

LaunchAgent:

```text
Label: dk.froekjaer.timelapse-headend
State: running
Program: /Users/peter/.venvs/timelapse-headend/bin/uvicorn
Working directory: /Users/peter/projects/timelapse-pro/headend
Resolved project path: /Volumes/data-fast/peter-home/projects/timelapse-pro
```

Health:

```text
http://127.0.0.1:8000/api/health -> 200 OK
https://timelapse.froekjaer.dk/ -> 200 OK
https://timelapse.froekjaer.dk/api/health -> 200 OK
```

### Storage efter flytning

Aktuelle mounts:

```text
/Volumes/data-fast  931 GiB, 28% brugt
/Volumes/Backup     931 GiB, 6% brugt
```

Projektplacering:

```text
/Users/peter/projects -> /Volumes/data-fast/peter-home/projects
```

Tidligere fejl i log:

```text
FileNotFoundError: /Volumes/data/Frøkjær
PermissionError: [Errno 13] Permission denied: /Volumes/data
```

Rettet DB-state:

```text
sftp_base        = /Volumes/data-fast
sftp_remote_base = /Volumes/data-fast/timelapse-incoming/sftp_nvj17c/data
backup_nas_path  = /Volumes/data-fast/backup
```

Skrivbarhedstest:

```text
write-ok /Volumes/data-fast/Frøkjær/Nordre_Villavej_17c/Kamera_1/2026/06/22
```

### Aktiv Edge

Aktiv Edge er:

```text
TL-C87FF9587CA0
IP: 192.168.86.134
Hardware: Orange Pi 4 Pro
Kamera: Nikon Z30
Headend last_seen: 2026-06-22 12:12
Edge service: active
```

Edge log viser:

- kamera detekteres som `Nikon Z30`
- capture gennemføres
- quality check passerer
- thumbnail og sidecar sendes med upload
- upload fejlede med `500` før storage-fixen
- samme capture blev retryet efter storage-fixen og uploadede med `200 OK`
- heartbeat og update policy virker

Efter storage-fix:

```text
2026-06-22 12:14:54 Capture API files received:
device=TL-C87FF9587CA0
filename=Frøkjær_Nordre_Villavej_17c_Kamera_1_20260622_100958.jpg
HTTP 200 OK
```

DB:

```text
capture_id=26083
uploaded=true
ai_analyzed_at=2026-06-22 12:15:07
```

### CMDB og updates

Update status:

```text
approved:    1
deployed:   19
rejected:    4
rolled_back: 2
```

Åben update:

```text
#33 os_updates, 59 pakker, approved/test/device, scope_id=TL-DCA63234D813
```

Vigtig konklusion: #33 er ikke til den aktive Edge. Den må ikke bruges som bevis for produktionsklar patching af `TL-C87FF9587CA0`.

Seneste app/artifact E2E fra 2026-06-21:

```text
#34 app_updates -> deployed på TL-C87FF9587CA0
Artifact: TL-QA-APP-20260621-150321
Change ticket: TL-CHG-20260621-00034
```

### AI/post-processing

Capture backlog:

```text
captures total: 25574
missing_ai:    2535
missing_tags:  3033
```

Dette er ikke en blocker for upload/drift, men det er en GRC-/datakvalitetsrisiko, fordi søgning, rapportering og AI-baseret udvælgelse ikke er komplet.

### Node-agent

Plist findes:

```text
/Library/LaunchDaemons/dk.froekjaer.timelapse-node-agent.plist
```

Men launchctl viser ikke servicen loaded i system domain, og loggen stopper:

```text
2026-06-22 07:46:53 Signal 15 modtaget - lukker ned
2026-06-22 07:46:55 Node Agent stoppet
```

Repo-koden er rettet til at foretrække `/Volumes/data-fast` over `/Volumes/data`. Den installerede `/opt/timelapse-node-agent/collectors/inventory.py` er root-ejet og blev ikke ændret i denne kørsel.

## SABSA reassessment

### Contextual layer - forretning og risikoejere

Business objective:

- Hurtigt få første rigtige site i drift med stabil capture, sikker update-governance og dokumenteret compliance posture.

Forretningsattributter:

| Attribut | Vurdering | Begrundelse |
|---|---|---|
| Availability | Gul | Headend er oppe, og capture upload virker igen efter storage path rettelse; mangler startup preflight for ekstern disk. |
| Integrity | Gul | Signed artifact-flow virker for app-test, men OS-flow mangler frisk E2E på aktiv Edge. |
| Confidentiality | Gul | Auth/RBAC er forbedret, men secrets findes stadig i DB/LaunchAgent miljø. |
| Accountability | Gul/grøn | Change ticket, artifact og per-target update evidence findes; node-agent er dog nede. |
| Maintainability | Gul | Ekstern disk løser kapacitet, men hardcodede `/Volumes/data` antagelser skal ryddes. |
| Compliance readiness | Gul | GRC cockpit og standardrapporter findes, men evidence-kilder er ikke alle friske. |

Risikoejere:

- Product owner: accepterer go/no-go for første site.
- Security/change owner: accepterer update-flow, key lifecycle og exposure.
- Operations owner: ejer storage, backup, monitoring og restore.
- Customer/site owner: accepterer auto-update policies og change windows.

### Conceptual layer - sikkerhedsstrategi

Strategisk model:

- Headend er update authority.
- Edge er reporter/puller, ikke update authority.
- Updates skal være signerede artifacts med change-ticket binding.
- Edge må ikke bruge direkte Internet/GitHub/apt i normal drift.
- Storage skal være managed asset med capacity, backup og mount health.
- AI-tags er derived metadata og må ikke være eneste compliance evidence.

Gaps:

- Storage-root er stadig spredt i kode, settings, site overrides og dokumentation.
- Node-agent er nødvendig som Headend CMDB evidence source, men er stoppet.
- Secrets model er praktisk, men ikke moden nok til et kundekontrolleret multi-headend setup.

### Logical layer - kontroller og arkitekturservices

Nødvendige logical services:

| Service | Status | Kommentar |
|---|---|---|
| Identity/RBAC | Delvist grøn | UI/API auth virker; CMDB anonymous lukket tidligere. |
| Device auth/HMAC | Gul/grøn | Aktiv Edge og Headend-agent er forbedret; legacy/stale credentials skal ryddes. |
| Update governance | Gul | App artifact E2E virker; OS E2E på aktiv Edge mangler. |
| CMDB | Gul | Aktiv Edge frisk; Mac Mini inventory stale pga. stoppet node-agent. |
| Storage service | Gul | Sti rettet, men skal centraliseres og overvåges. |
| Backup/restore | Gul | Backup-sti rettet; restore-test/evidence mangler. |
| AI metadata pipeline | Gul/rød | Backlog på AI/tags og tidligere hallucinationer kræver cloud/ontology/review-model. |
| SIEM | Gul/grøn | Edge og Headend sender events; node-agent stoppet reducerer host evidence. |

### Physical layer - platform og netværk

Aktuel fysisk/logisk platform:

- Mac Mini Headend med ekstern APFS disk `/Volumes/data-fast`.
- Separat `/Volumes/Backup`.
- Headend process som user LaunchAgent.
- Aktiv Edge Orange Pi 4 Pro med Nikon Z30.
- Public adgang via `https://timelapse.froekjaer.dk`.

Risici:

- Ekstern disk mount-navn er nu en kritisk dependency.
- Hvis `/Volumes/data-fast` ikke monteres før Headend starter, kan uploads fejle.
- Root-owned installeret node-agent gør hurtige rettelser vanskeligere.
- Local/public routing afhænger af nginx/Cloudshare/DNS-portmapping, som bør dokumenteres som production asset.

### Component layer - konkrete komponenter

Kritiske komponenter:

| Komponent | Status | Næste handling |
|---|---|---|
| Headend FastAPI | Grøn/gul | Kører; tilføj startup preflight for storage-root. |
| PostgreSQL | Grøn | Svarer; bruges som source of truth. |
| nginx/public UI | Grøn | Public health og root svarer 200. |
| Edge agent | Gul/grøn | Kører; upload skal genbekræftes efter storage-fix. |
| Node-agent | Rød | Ikke loaded/running efter kl. 07:46. |
| Artifact store | Gul | E2E app artifact virker; gamle image artifacts ligger på `/tmp` og bør arkiveres/ryddes. |
| Backup | Gul | Path rettet; restore-test mangler. |
| AI/Ollama | Gul | Bør være tool til CMDB/SIEM, ikke autoritativ billedtagging. |

### Operational layer - drift, overvågning og runbooks

Driftsstatus:

- Headend er oppe.
- Public UI/API er oppe.
- Aktiv Edge er oppe og tager billeder.
- Seneste fejlede upload er retryet og bekræftet uploaded efter storage-fix.
- Node-agent er nede.
- Update #33 for stale Edge kan skabe støj i operator-flowet.

Nødvendige runbooks:

1. Mac reboot/startup med ekstern disk:
   - valider mount
   - valider Headend venv
   - valider PostgreSQL
   - valider nginx
   - valider Headend health
   - valider test-write til capture-root
   - valider Edge upload

2. Storage migration:
   - single source of truth for storage root
   - DB settings
   - site overrides
   - node-agent inventory
   - backup path
   - documentation
   - old paths detection

3. Production update:
   - lab test
   - signed artifact
   - change ticket
   - approval
   - Edge pull
   - backup
   - deployed evidence
   - rollback evidence

## Prioriteret mangelliste

### P1 - før første rigtige site

1. Genetabler Mac Mini node-agent og få frisk inventory med `/Volumes/data-fast`.
2. Tilføj Headend startup/preflight check for storage-root:
   - path exists
   - writable
   - enough free space
   - expected mount UUID
3. Ryd eller isolér update #33, fordi den peger på stale Edge `TL-DCA63234D813`.
4. Gennemfør backup + restore-test til `/Volumes/Backup`.
5. Få Nikon Z30 kamera-config drift under kontrol eller marker forventet drift som accepteret.

### P2 - production hardening

1. Centraliser storage root i én konfigurationsmodel i stedet for hardcoded `/Volumes/data`.
2. Flyt runtime secrets mod Keychain/secret manager eller krypteret settings-model.
3. Gør stale device status freshness-baseret i alle UI-flader.
4. Gennemfør OS offline artifact E2E på aktiv lab/staging Edge.
5. Gør post-processing idempotent og batch-styret for thumbnails/AI/tags.
6. Ryd gamle artifacts på `/tmp` eller flyt dem til persistent artifact storage.

### P3 - modenhed

1. Formalisér SABSA business attribute profile pr. kunde/site.
2. Knyt GRC dashboard direkte til quantitative risk og change evidence.
3. Tilføj kundeaccept via mail/API/ticket integration.
4. Gør multi-headend/multi-customer promotion flow eksplicit.
5. Etabler cloud vision pipeline med fast engelsk tag-ontologi og dansk oversættelsestabel.

## Go/no-go vurdering

### Go for lab fortsættelse

Ja. Systemet er godt nok til fortsat lab-test og kontrolleret site-forberedelse.

### Go for første rigtige site

Næsten, men jeg ville stadig lukke disse først:

- node-agent frisk Mac inventory
- startup preflight for ekstern disk
- backup/restore evidence
- beslutning om stale Edge/update #33

### Go for internet-facing production

Ikke endnu. Public UI svarer, men før egentlig production exposure skal secrets, stale credentials, storage preflight, backup/restore og GRC evidence lukkes mere systematisk.

## Ændringer udført under denne reassessment

1. Rettet DB settings fra `/Volumes/data` til `/Volumes/data-fast`:
   - `sftp_base`
   - `sftp_remote_base`
   - `backup_nas_path`
2. Rettet site override for `Nordre Villavej 17c` til `/Volumes/data-fast`.
3. Genstartet Headend LaunchAgent.
4. Verificeret `/api/health`.
5. Verificeret write-adgang til ny canonical capture-sti.
6. Rettet repo-version af `node-agent/collectors/inventory.py`, så macOS foretrækker `/Volumes/data-fast`.
7. Verificeret at Edge-capture upload retry lykkedes efter storage-fix, og at Gemini analyserede capture `26083`.

## Åbne tekniske noter

- Den installerede `/opt/timelapse-node-agent/collectors/inventory.py` er ikke ændret, fordi den er root-ejet.
- Node-agent plist findes, men servicen er ikke loaded i launchctl efter stoppet kl. 07:46.
- Headend log indeholder gamle `/Volumes/data` stack traces fra før rettelsen; nye logs efter restart viser normal startup.
- API `/api/admin/stats` returnerer `401` uden login, hvilket er korrekt.
