# Codex kode-/driftsvalidering for v11

Dato: 2026-07-02 22:39-22:48 CEST
Udført af: Codex
Formål: Validere om dokumentpakken kan løftes til v11 uden at gøre historiske eller ønskede tilstande til aktiv "sandhed".

## Konklusion

Nej til mekanisk v11-bump af alle dokumenter uden rettelser.

Ja til v11-runde dokument-for-dokument, hvis nedenstående fund enten:

- rettes i kode/drift først,
- beskrives som kendt restpunkt,
- eller markeres tydeligt som historik/planlagt arbejde.

Systemet kører og har et stærkt fundament: headend API, UI, nginx, PostgreSQL, Ollama og Orange Pi edge-service er live. Canon/Nikon-sporet, SFTP via DB-settings, canonical image storage og NPU-værktøjskæden findes. Men flere dokumentpåstande vil være for stærke, hvis de skrives som fuldt produktionsklare allerede nu.

## Valideret driftstilstand

Live-tjek på Mac Mini/headend:

- Headend API svarer på `http://127.0.0.1:8000/api/health` med `{"status":"ok"}`.
- `dk.froekjaer.timelapse-headend` kører via uvicorn på `127.0.0.1:8000`.
- UI dev server kører på `127.0.0.1:5173`.
- nginx kører og lytter på `*:80` og `*:443`.
- PostgreSQL 17.10 kører på `127.0.0.1:5432`.
- Ollama kører på `127.0.0.1:11434`.
- Syslog receiver kører på `127.0.0.1:5514`.
- Reverse SSH-forwarding er aktiv på port `2201` og `2202`.

Live-tjek på Orange Pi:

- Orange Pi `timelapse0101` svarer på SSH som `orangepi@192.168.86.134`.
- Kernel: Linux 5.15.147 sun60iw2 aarch64.
- `timelapse-edge` systemd-service er aktiv.
- `timelapse-node-agent` systemd-service er inaktiv på Orange Pi.
- `/opt/timelapse/bin/edge_qa_viplite` findes.
- `/opt/timelapse/models/edge_qa.nb` og flere `.nb` testmodeller findes.

Storage:

- `/Volumes/data-fast` er mounted og har ca. 606 GiB fri.
- `/Volumes/Backup` er mounted, men ca. 86% brugt.
- Canonical images root findes på `/Volumes/data-fast/timelapse-incoming/canonical-images`.

## Valideret database/status

PostgreSQL `timelapse_db`:

- `captures`: 27.608 rækker.
- `devices`: 9 rækker.
- `customers`: 5 rækker.
- `sites`: 4 rækker.
- `cameras`: 5 rækker.

Capture-fordeling:

- `TL-C87FF9587CA0`: 21.451 captures fra 2026-04-01 til 2026-07-02.
- `TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_1`: 5.029 captures fra 2022-01-26 til 2026-05-08.
- `TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_2`: 1.129 captures fra 2022-01-26 til 2026-07-02.

Kameramodeller i captures:

- `TL-C87FF9587CA0`: 14.491 med `Canon EOS 1300D`.
- `TL-C87FF9587CA0`: 6.960 med `Nikon Z30`.
- Travbyen importer har tom `camera_model`.

Aktiv edge-device:

- `TL-C87FF9587CA0` er online og har frisk `last_seen`.
- Men `devices.hardware_model` og `devices.camera_model` er tomme for den aktive edge.

Settings:

- `sftp_enabled=true`.
- `sftp_host=timelapse.froekjaer.dk`.
- `sftp_port=22222`.
- `sftp_remote_base=/Volumes/data-fast/timelapse-incoming/canonical-images`.

Users/MFA:

- `operator`: 1 bruger, 0 med MFA.
- `super_admin`: 4 brugere, 0 med MFA.

## Kodevalidering

Kamera- og edge-spor:

- `edge/camera/drivers/gphoto2_driver.py` har profiler for generisk gPhoto2, Canon EOS og Nikon Z30.
- Driverkommentar nævner test med Canon EOS 1300D, Canon EOS 2000D, Canon EOS 800D og Nikon Z30.
- Nikon Z30-profil indeholder remote focus/liveview/movie/action controls.
- `edge/diagnostics/camera_diagnostics.py` har shutter ratings for Canon EOS 1300D, 2000D, 250D, 90D og 5D Mark IV.
- Canon EOS 1000D og Nikon Z30 mangler eksplicit shutter-rating i diagnostics og falder derfor tilbage på default.

UI:

- `timelapse-ui/src/pages/DevicePage.tsx` har stadig hardcoded tekst `Kamera - Canon EOS 1300D`.
- Det skal gøres dynamisk før dokumentationen siger, at UI fuldt understøtter Canon 1000/1300/2000 og Nikon Z30 side om side.

RBAC/API:

- Koden indeholder rollekrav, tenant/customer scoping helpers og HMAC-request-signatur for edge/API-flows.
- `devices` har `customer_id`, `site_id`, `tenant_id`, `camera_index`.
- `cameras` har `customer_id`, `site_id`, `config` og device-/sitebinding.
- `captures` er fortsat primært `device_id`-baseret og har ikke direkte `customer_id`.
- Derfor skal v11 beskrive RBAC som API-/join-baseret tenant scoping, ikke som en fysisk sikkerhedsgaranti alene på `captures.customer_id`.

SFTP/storage:

- SFTP-settings er DB-drevne og peger live på `/Volumes/data-fast/...`.
- nginx X-Accel alias peger også på canonical image root.
- Dette matcher NAS/mapped-drive-strategien, men v11 bør kræve en dokumenteret mount-switch-test før prod.

NPU/AI:

- Orange Pi har NPU-wrapper og `.nb` modeller installeret.
- Mini `edge_cnn`-sporet er brugbart som NPU-parity baseline.
- Den større real-world QA-model er ikke klar til drift: real-world-only træning blev stoppet pga. ustabilitet, og tidligere holdout-model viste domain gap på Travbyen.
- v11 må gerne beskrive NPU-pipelinen som etableret, men ikke som færdig produktionsmodel.

## V11-blokkere eller kræver tydelig markering

1. **Offentlig nginx-portstatus**
   - Live nginx lytter stadig på `*:80` og `*:443`.
   - Dokumenter må ikke påstå, at prod-portmodellen med kun Cloudflare/loopback er aktiv, før den faktisk er rullet ud.

2. **MFA**
   - Ingen nuværende brugere har MFA slået til.
   - Security/Compliance/RBAC-dokumenter bør markere MFA som restpunkt eller aktiveres før v11-go-live.

3. **Orange Pi node-agent**
   - `timelapse-edge` er aktiv, men `timelapse-node-agent` er inaktiv på Orange Pi.
   - Dokumenter skal skelne mellem edge-service, Mac/headend node-agent og eventuel Orange Pi node-agent.

4. **Aktiv device metadata**
   - `TL-C87FF9587CA0` er online, men mangler `hardware_model` og `camera_model` i `devices`.
   - CMDB/System Inventory bør ikke påstå fuld hardware-inventory-kvalitet, før collector/backfill opdaterer dette.

5. **Dynamisk kameramodel i UI**
   - DevicePage har hardcoded Canon EOS 1300D overskrift.
   - Ret før v11 siger fuld Nikon Z30/Canon multi-camera support i UI.

6. **Camera diagnostics supportmatrix**
   - Canon EOS 1000D og Nikon Z30 mangler eksplicit shutter-rating/diagnostic modeldata.
   - Kan være acceptabelt med default, men dokumentationen skal kalde det "generic fallback" hvis ikke rettet.

7. **AI/NPU-produktionsstatus**
   - NPU toolchain og runtime er installeret.
   - Production-grade QA-model er ikke valideret på Travbyen real-world data endnu.

8. **Backup/restore**
   - Backup volume findes, men er 86% fuld.
   - Restore-test er ikke valideret i denne runde.

9. **Tenant isolation test**
   - RBAC/scoping er til stede i kode, men der mangler en eksplicit endpoint-by-endpoint integrationstest, der beviser at kunde A ikke kan læse kunde B billeder/API-data.

## Dokumentkonsekvens

Disse dokumenter bør først have v11 efter målrettet opdatering:

- `SERVICES_OG_DRIFT_kilde_til_sandhed.md`
- `System_Inventory_v10.md`
- `RBAC_Remote_Operational_v10.md`
- `TimeLapse_Security_Compliance_v10.md`
- `PORT_AUDIT_og_WEBSITE_v10.md`
- `GO_LIVE_CHECKLIST_v10.md`
- `TimeLapse_Edge_Runbook_v10.md`
- `Installationsguide_v10.md`
- `Timelapse_pro_full_documentation_v10.md`

Særlige rettelser:

- Fjern/arkiver aktiv reference til gammel RPI5 headend som aktuel arkitektur.
- Brug Mac Mini/headend + Orange Pi 4 Pro edge som aktiv referencearkitektur.
- Beskriv Canon EOS 1000D/1300D/2000D og Nikon Z30 som supportmatrix med status pr. model:
  - driver/profil,
  - live testet,
  - diagnostics komplet,
  - UI dynamisk,
  - kendte begrænsninger.
- Dokumenter mapped/NAS-drive-dynamik som DB-konfigureret storage-root og SFTP-root, med krav om mount-switch-test.

## Anbefalet næste rækkefølge

1. Ret DevicePage til dynamisk kameramodel.
2. Tilføj/backfill aktiv `devices.hardware_model` og `devices.camera_model`.
3. Tilføj diagnostics entries eller eksplicit fallback for Canon EOS 1000D og Nikon Z30.
4. Lav API/RBAC integrationstest for cross-customer image access.
5. Verificer SFTP/API access efter storage-root/mount switch.
6. Lav dokumenteret backup/restore smoke test.
7. Markér NPU QA som "runtime/pipeline etableret, model under tuning" indtil Travbyen real-world score er god nok.
8. Opdater v10-dokumenter til v11 enkeltvis med valideringsstatus i toppen.

## Godkendelsesregel for v11

Et dokument må blive v11, når det har:

- "Valideret mod kode/drift" dato og initialer.
- Liste over eventuelle kendte afvigelser.
- Ingen historiske påstande skrevet som aktiv drift.
- Ingen sikkerheds- eller adgangspåstande uden enten live-test, kodehenvisning eller tydeligt restpunkt.
