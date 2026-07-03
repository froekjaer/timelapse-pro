# TimeLapse Pro - Administratormanual

**Dato:** 2026-06-23  
**Målgruppe:** Systemadministrator, teknisk drift, sikkerhedsansvarlig og projektadministrator  
**Status:** Pre-production. Bruges sammen med `GO_LIVE_CHECKLIST_2026-06-23.md`.

## 1. Daglig drift

Kontroller dagligt:

- Headend health: `/api/health`
- aktiv edge status og seneste heartbeat
- seneste capture/upload
- CMDB inventory freshness
- backupstatus
- update-flow status
- postprocessing backlog
- GRC/compliance findings

Aktiv R&D/test edge pr. 2026-06-23 er `TL-C87FF9587CA0`.

## 2. Headend

Headend kører på Mac Mini:

- FastAPI/uvicorn på `127.0.0.1:8000`
- PostgreSQL på loopback
- nginx som reverse proxy i lab
- Ollama på `127.0.0.1:11434`
- storage på `/Volumes/data-fast`
- backup target på `/Volumes/Backup`

Før production skal Headend have startup-preflight:

- `/Volumes/data-fast` monteret
- forventet mount/UUID
- skriveadgang til capture-root
- nok ledig disk
- PostgreSQL kører
- nginx kører på korrekt portmodel
- node-agent kører

## 3. Brugere, RBAC og MFA

Roller:

- `super_admin`
- `admin`
- `technician`
- `viewer/customer`

Adminopgaver:

1. Opret bruger.
2. Tildel rolle og eventuelt kunde-scope.
3. Aktivér MFA/WebAuthn når funktionen er fuldt production-ready.
4. Gennemgå brugerlisten jævnligt.
5. Fjern eller deaktivér brugere, der ikke længere skal have adgang.

Før Internet-go-live skal super_admin-password være ændret fra default, og højrisiko-operationer bør kræve MFA.

## 4. Kunde, site og kamera

TimeLapse Pro skelner mellem fysisk edge og logisk kamera-lokation:

- `devices`: fysisk edge/node
- `cameras`: logisk kamera-lokation
- `device_assignments`: binding mellem edge og kamera-lokation

Ved ny installation:

1. Opret kunde.
2. Opret site.
3. Opret kamera-lokation.
4. Generér bootstrap token til edge.
5. Klargør edge image eller lokal provisioning.
6. Bind edge til kamera-lokation.
7. Verificér første heartbeat.
8. Verificér første preview/full capture/upload.

## 5. Global Config

Konfiguration arves i fire lag:

```text
global -> kunde -> site -> kamera
```

Lavere lag vinder over højere lag. UI'et skal vise:

- arvet værdi
- direkte værdi på laget
- effektiv værdi
- hvilket lag der vinder
- farvemarkering for overrides og afvigelse fra global

Brug kamera-laget til site-/kamera-specifikke justeringer som relay power, ISO, fokusstrategi og storage overrides.

## 6. Nikon Z30 og LAB

Nikon Z30 er nu primær kameratype. Profilen skal udnytte:

- remote focus
- focus slice
- liveview/video-stream
- ISO, lukker, blænde, hvidbalance og billedformat
- lokal edge quality/focus-test

LAB-procedure:

1. Start LAB mode.
2. Verificér at relay er tændt og kameraet er tilgængeligt.
3. Kør preview.
4. Kør full capture.
5. Kør autofocus/focus slice/focus quality test.
6. Justér kamera-parametre.
7. Gem ønsket config på kamera-laget.
8. Stop LAB mode.

Kendte åbne punkter:

- live video-stream skal færdiggøres via reverse SSH extra forward
- Nikon focus step og focus slice skal production-testes
- readonly/enforceable kameraværdier skal markeres tydeligt
- accepted equivalent labels skal håndtere fx `AWB White` vs. `Automatic`

## 7. Update-flow

Grundregel: Edge må ikke selv hente updates fra Internet, GitHub eller eksterne apt repositories i production.

Korrekt flow:

1. Edge/node-agent rapporterer inventory til CMDB.
2. Headend reconciler installeret state mod update-katalog.
3. Headend opretter update-kandidat.
4. Artifact bygges i lab/test.
5. Artifact signeres og registreres i Headend.
6. Change ticket oprettes og bindes til artifact.
7. Testmiljø godkender og installerer.
8. Efter QA kan update promoveres til staging/prod.
9. Edge poller policy.
10. Edge downloader kun filer fra Headend artifact-katalog.
11. Edge verificerer manifest, hash og signer.
12. Edge tager pre-update backup.
13. Edge installerer offline/lokalt.
14. Edge rapporterer deployed/failed/blocked.
15. Headend opdaterer CMDB, update status og audit.

OS bundles må kun bruge `apt-get --no-download` til lokal dependency fix. `apt-get update`, `apt-get upgrade`, `dist-upgrade` og `full-upgrade` er ikke production-kompatible på edge.

## 8. Backup og restore

Backup skal være dokumenteret før production:

- Headend backup til `/Volumes/Backup`
- Edge backup via Headend/UI
- database backup
- konfigurationsbackup
- artifact backup
- restore-test med dokumenteret RTO/RPO

Minimum restore-test:

1. Tag backup.
2. Verificér backupfil og checksum.
3. Restore til testplacering.
4. Start Headend mod restored data eller valider database dump.
5. Dokumentér resultat i GRC/evidence.

## 9. Edge image build

Edge disk images bygges fra UI/admin-flow og gemmes i persistent artifact storage:

- target: Orange Pi 4 Pro m.fl.
- bootstrap token kan injiceres
- WiFi kan injiceres
- SSH keys kan injiceres
- manifest og SBOM genereres
- `.img.gz` skal kunne vælges og downloades fra UI

Før image bruges i production:

- build log gemmes
- manifest og SHA-256 gemmes
- SBOM gemmes
- bootstrap token er tidsbegrænset/engangsbrug
- image testes i lab

## 10. CMDB og SBOM

CMDB skal vise:

- installeret OS og version
- installerede systempakker
- installerede Python/venv pakker
- Timelapse Pro version
- hardware model
- firmware/kernel
- seneste tilgængelige version
- risikoklassifikation
- update status

SBOM skal genereres ved:

- Edge image build
- Timelapse Pro release
- OS bundle build
- større Headend dependency update

SBOM og artifact skal linkes til change ticket.

## 11. GRC og compliance

Compliance dashboardet skal bruges til:

- SABSA business attributes
- ISO 27001 control evidence
- IEC 62443 zones/conduits og patching
- CRA secure update/SBOM/lifecycle evidence
- NIS2 risk/continuity/supply-chain evidence
- GDPR DPIA/retention/access evidence

Før første kunde-site:

- DPIA-template skal være klar
- retention policy pr. kamera skal kunne sættes
- databehandleraftale-template skal være klar
- subprocessor-liste skal være dokumenteret, især Gemini/Google Cloud

## 12. Internet-go-live

Brug `GO_LIVE_CHECKLIST_2026-06-23.md` som gate.

Blockere pr. 2026-06-23:

- nginx lytter stadig på `*:80` og `*:443` i lab
- backup + restore-test mangler
- node-agent frisk inventory mangler
- GDPR DPIA/retention mangler
- stale credentials skal ryddes/migreres

Anbefalet domænemodel:

- `www.timelapse-pro.dk`: offentlig informationsside
- `backend.timelapse-pro.dk`: TimeLapse Pro UI/API bag Cloudflare Tunnel
- Mac Headend-origin på `127.0.0.1:18443`

## 13. Incident response

Ved sikkerhedshændelse:

1. Stop yderligere eksponering, hvis nødvendigt.
2. Bevar logs og artifacts.
3. Identificér berørte kunder/sites/billeder.
4. Roter relevante credentials.
5. Dokumentér hændelsen i GRC.
6. Vurder GDPR Art. 33/34 anmeldelse inden 72 timer.
7. Udfør root cause og corrective action.

## 14. Kendte tekniske gældspunkter

- `slowapi` importeres i backend men mangler i `headend/requirements.txt`.
- deploy LaunchAgent template er ikke opdateret til den aktive venv/model.
- frontend lint baseline er ikke grøn.
- Open WebUI skal besluttes som prod-komponent eller lab-only.
- postprocessing af manglende thumbnails skal gøres robust.
- per-target update status skal vises mere tydeligt i UI.
- intern CA/mTLS er ikke implementeret.

