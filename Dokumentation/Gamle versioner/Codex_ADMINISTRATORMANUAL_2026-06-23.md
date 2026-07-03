# Codex - TimeLapse Pro administratormanual

**Forfatter:** Codex  
**Dato:** 2026-06-23  
**Maalgruppe:** Systemadministrator, drift, sikkerhedsansvarlig og teknisk projektleder.

## 1. Daglig driftskontrol

Kontroller:

- Headend `/api/health`
- seneste Edge heartbeat
- seneste capture/upload
- CMDB inventory freshness
- backupstatus
- update-flow status
- postprocessing backlog
- GRC/compliance findings
- diskplads paa `/Volumes/data-fast` og `/Volumes/Backup`

Aktiv R&D/test Edge: `TL-C87FF9587CA0`.

## 2. Headend

Aktuel arkitektur:

- FastAPI/uvicorn paa `127.0.0.1:8000`
- PostgreSQL paa loopback
- nginx som lab reverse proxy
- Ollama paa `127.0.0.1:11434`
- storage paa `/Volumes/data-fast`
- backup target paa `/Volumes/Backup`

Foer production skal Headend have startup-preflight:

- storage mount findes
- mount er skrivbart
- tilstraekkelig diskplads
- PostgreSQL koerer
- Headend health svarer
- node-agent koerer
- nginx portmodel er prod-kompliant

## 3. Brugere og RBAC

Admin skal:

1. Oprette brugere med korrekt rolle.
2. Scope brugere til kunde/site hvor relevant.
3. Aktivere MFA/WebAuthn for admin/high-risk operationer.
4. Fjerne brugere der ikke laengere har behov.
5. Gennemgaa audit logs.

Roller:

- `super_admin`
- `admin`
- `technician`
- `viewer/customer`

## 4. Kunde, site, kamera og Edge

TimeLapse Pro skelner mellem:

- `devices`: fysisk Edge/node
- `cameras`: logisk kamera-lokation
- `device_assignments`: binding mellem Edge og kamera-lokation

Ny installation:

1. Opret kunde.
2. Opret site.
3. Opret kamera-lokation.
4. Generer bootstrap token.
5. Klargoer Edge image eller lokal provisioning.
6. Bind Edge til kamera-lokation.
7. Verificer heartbeat.
8. Verificer preview, full capture og upload.

## 5. Global Config

Konfiguration arves:

```text
global -> kunde -> site -> kamera
```

Lavere lag vinder. UI skal vise:

- arvet vaerdi
- direkte override
- effektiv vaerdi
- vindende lag
- farvemarkering for afvigelse fra global

Brug kamera-laget til kamera-/site-specifikke valg som relay, ISO, fokusstrategi og Nikon Z30-profildata.

## 6. Nikon Z30 og LAB

Nikon Z30 er ny primær kameratype.

LAB-procedure:

1. Start LAB mode.
2. Verificer relay og kamera-tilgaengelighed.
3. Koer preview.
4. Koer full capture.
5. Test autofocus/focus slice/focus quality.
6. Juster parametre.
7. Gem config paa korrekt lag.
8. Stop LAB mode.

Kendte aabne punkter:

- video stream via reverse SSH extra forward
- focus step/focus slice QA
- readonly vs enforceable settings
- accepted labels, fx `AWB White` vs `Automatic`

## 7. Update-flow

Edge maa ikke hente production updates direkte fra Internet, GitHub eller eksterne apt repositories.

Korrekt flow:

1. Edge/node-agent rapporterer inventory til CMDB.
2. Headend reconciler mod update-katalog.
3. Headend opretter update-kandidat.
4. Artifact bygges og testes i lab.
5. Artifact signeres og registreres.
6. Change ticket oprettes.
7. Update godkendes til test/staging/prod.
8. Edge poller policy.
9. Edge downloader artifact fra Headend.
10. Edge verificerer manifest, hash og signer.
11. Edge tager pre-update backup.
12. Edge installerer offline/lokalt.
13. Edge rapporterer status.
14. Headend opdaterer CMDB og audit.

OS bundles maa kun bruge `apt-get --no-download` til lokal dependency fix. `apt-get update`, `apt-get upgrade`, `dist-upgrade` og `full-upgrade` er ikke tilladt paa Edge i production.

## 8. Backup og restore

Foer production:

- Headend backup skal koere.
- Edge backup skal kunne startes/følges fra UI.
- Database backup skal verificeres.
- Restore-test skal gennemfoeres og dokumenteres.
- RTO/RPO skal defineres.

Minimum restore-test:

1. Tag backup.
2. Verificer checksum.
3. Restore til testplacering.
4. Valider database og filstruktur.
5. Dokumenter resultat i GRC/evidence.

## 9. Edge image build

Edge images skal:

- bygges fra UI/admin-flow
- gemmes som artifacts
- have manifest og SHA-256
- indeholde SBOM
- kunne downloades fra UI
- bruge tidsbegraenset/engangs bootstrap token
- testes i lab foer site deployment

## 10. CMDB, SBOM og GRC

CMDB skal vise:

- installeret OS/software
- senest tilgaengelig version
- security/functional update status
- Edge/Headend hardware og firmware
- risk score
- evidence freshness

SBOM skal linkes til:

- Edge image
- app release
- OS bundle
- change ticket

GRC skal kunne rapportere mod SABSA, ISO 27001, IEC 62443, CRA, NIS2 og GDPR.

## 11. Internet go-live

Brug `Codex_GO_LIVE_CHECKLIST_2026-06-23.md` som gate.

Blockere:

- nginx lab bruger public 80/443
- backup + restore-test mangler
- node-agent frisk inventory mangler
- GDPR DPIA/retention/DPA mangler
- stale credentials skal ryddes
- MFA/WebAuthn-governance mangler

Target:

- `www.timelapse-pro.dk`: statisk public website
- `backend.timelapse-pro.dk`: TimeLapse UI/API bag Cloudflare Tunnel
- Mac Headend-origin: `127.0.0.1:18443`

## 12. Incident response

Ved mulig sikkerhedshaendelse:

1. Stop yderligere eksponering om noedvendigt.
2. Bevar logs og evidence.
3. Identificer berorte kunder/sites/billeder.
4. Roter credentials.
5. Dokumenter haendelsen i GRC.
6. Vurder GDPR Art. 33/34 anmeldelse inden 72 timer.
7. Udfør root cause og corrective actions.

