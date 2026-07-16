# 00 — START HER (master-indeks & onboarding)

> **GRC single source of truth:** Testcases, testkørsler, risici, fund,
> afhjælpninger og evidens vedligeholdes i PostgreSQL og vises under
> `Compliance -> GRC register`. Markdown-test- og riskdokumenter er
> migreringskilder, runbooks eller genererede rapporter, ikke aktiv status.

**Formål:** Indgangsdokumentet til TimeLapse Pro-dokumentationen. Læs dette først når du starter en ny session (Claude, Codex eller menneske). Det peger på den seneste, autoritative version af hvert dokument (`\*\_v10.md`), de levende arbejdsdokumenter og den underliggende empiri. **Sidst opdateret:** 2026-07-03 **Vedligeholdelsesregel:** Én seneste version pr. dokument, vedligeholdt som `.md`. Ved væsentlig opdatering hæves versionen og forgængeren flyttes til `Gamle versioner/`. Opdatér denne fil når nye autoritative dokumenter kommer til.


## 1. Boot en ny session — kernefakta

**Projektprincipper (fra CLAUDE.md):** Senior programmør-niveau. SABSA-ekspert; forstår ISO 27000, IEC 62443, CRA, GDPR. **Dobbelttjek før du udfører.** Ændringer er additive + flag-guardede; ingen skema-brud før live-verifikation; **aldrig hard-delete** (brug quarantine/reversible flyt); rør ikke den andens (Codex') ucommittede arbejde stiltiende.

**Bindende arkitektur (accepterede ADR'er — se `Dokumentation/ADR/`):** Enhver session er bundet af accepterede ADR'er. **ADR-001 (Accepted 2026-07-16): Platform/Payload-snit** — den non-funktionelle kerne (identitet, config, OTA, telemetri, remote access, HAL, sikkerhed, storage) er genbrugelig platform; den funktionelle del (i dag kamera/timelapse) er en udskiftelig payload, koblet via en versioneret `PayloadDriver`-kontrakt + capability manifest med reel proces-isolation, control/data-plane-adskillelse, fail-closed privilegier og JIT-conduits. Nye endpoints hører IKKE i `headend/main.py`. Se ADR-001 + `Arkitektur/Modularisering_Platform_Payload_Plan.md`. Samarbejdsregler: `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md`.

**Aktuel systemtopologi:**

- **Repo:** `~/projects/timelapse-pro` (= `/Volumes/data-fast/peter-home/projects/timelapse-pro`).

- **Headend (prod):** Mac Mini — FastAPI/uvicorn på `127.0.0.1:8000`, PostgreSQL `timelapse\_db`, nginx, UI på `127.0.0.1:5173`, Ollama `127.0.0.1:11434`. Kritiske services kører som system-LaunchDaemons: `dk.froekjaer.timelapse-headend`, `dk.froekjaer.timelapse-postgresql`, `dk.froekjaer.timelapse-nginx`, `dk.froekjaer.timelapse-ui`, `dk.froekjaer.timelapse-wifi-ensure`. Venv `~/.venvs/timelapse-headend`.

- **Storage:** `/Volumes/data-fast` (canonical). Billed-rod = `sftp\_base` fra DB-settings (`/Volumes/data-fast/timelapse-incoming/canonical-images`). Backup-target `/Volumes/Backup`.

- **Aktiv edge:** `TL-C87FF9587CA0` (Orange Pi 4 Pro, Nikon Z30). Stale/legacy: `TL-DCA63234D813`.

- **AI-tagging:** Gemini 2.5 Flash (Vertex, europe-west1) + Gemini Batch API (~50% pris); lokal Ollama til tekst/oversættelse. Canonical tags engelsk, danske labels via `ai\_tag\_vocabulary.display\_name\_da`.

- **Public (planlagt):** `www.timelapse-pro.dk` (statisk info, hostes separat fra staging/prod) + `backend.timelapse-pro.dk:8443` (UI/API, direkte nginx-eksponering — IKKE Cloudflare Tunnel, da CrushFTP allerede ejer 21/22/80/443 på staging/prod-maskinerne; certifikat via DNS-01, se `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4). Lab i dag: `timelapse.froekjaer.dk`.

**Status i én sætning:** LAB/pre-production-klar; **ikke** Internet-facing production-klar. Største blockere: port-/proxy-migration, backup+restore-evidens, GDPR (DPIA/retention/DPA), frisk CMDB/node-agent, MFA + stale credential-cleanup, Nikon Z30 LAB/fokus/video.

**Vigtigt om UI-drift (opdateret 2026-07-14):**

- Nginx på `timelapse.froekjaer.dk` serverer aktuelt den statiske produktionsbuild fra `~/projects/timelapse-pro/timelapse-ui/dist`.
- Vite dev-serveren kører også på `127.0.0.1:5173`, men offentlig `/` trafik proxyes normalt ikke direkte til den.
- Hvis `https://timelapse.froekjaer.dk/` giver `500 Internal Server Error`, mens `https://timelapse.froekjaer.dk/api/health` svarer `200`, så er backend typisk sund, og første kontrol er om `timelapse-ui/dist/index.html` findes.
- Kendt fejlmønster: manglende `dist/index.html` giver nginx-loggen `rewrite or internal redirection cycle while internally redirecting to "/index.html"`.
- Standardfix efter UI-ændringer eller manglende `dist`: `cd ~/projects/timelapse-pro/timelapse-ui && npm run build`.
- Hurtig validering:
  ```bash
  curl -skI https://timelapse.froekjaer.dk/
  curl -sk https://timelapse.froekjaer.dk/api/health
  tail -50 /opt/homebrew/var/log/nginx-timelapse-error.log
  ```


Tilføjet af Peter:

Som ny i vores projekt (~/projects/timelapse-pro/Documentation), vil jeg gerne bede dig om at tage et kig i alt dokumentationen, så jeg er sikker på at du er up-to-date, og jeg vil også gerne at du kigget sourcekoden igennem med nye øjne, og ser om der er noget der trænger til at blive optimeret mv. Da du er ny, vil jeg gerne at du i første omgang kigger, og rapportere. Så tager vi den lige sammen, alle tre Dig, mig og Codex. Du må gerne være meget kritisk. Husk at SABSA, COBIT, ISO27000, IEC62443, CRA, GDPR, AI act og NIS2 er dine kerne kompetencer, og samtidig er du vores nye stjerne arkitekt og senior programmør



## 2. Autoritative dokumenter (seneste = v10)

| Dokument | Emne |
| - | - |
| `Timelapse\_pro\_full\_documentation\_v10.md` | Samlet systemdokumentation — start her for helheden |
| `RISK\_ASSESSMENT\_v10.md` | SABSA/ISO/IEC 62443/CRA/NIS2/GDPR risikovurdering + pentest + PKI/Key Mgmt |
| `KRAVREGISTER\_og\_STATUS\_v10.md` | Krav-/ønskeregister, status, tidslinje, oprindelige krav, P0/P1/P2 |
| `GO\_LIVE\_CHECKLIST\_v10.md` | Krav (A–L) før Internet-eksponering + go/no-go |
| `PORT\_AUDIT\_og\_WEBSITE\_v10.md` | Portaudit, port 8443 + DNS-01-migration (IKKE Cloudflare Tunnel), website/backend-arkitektur |
| `Installationsguide\_v10.md` | **Del A: headend-installation · Del B: edge-installation · Del C: edge lokal provisioning** |
| `ADMINISTRATORMANUAL\_v10.md` | Drift, sikkerhed, update, backup, CMDB, RBAC, GRC, troubleshooting |
| `BRUGERMANUAL\_v10.md` | Bruger/kunde/site manager-manual |
| `Update\_Flow\_v10.md` | Update-flow: E2E QA, brugermanual, gates, API, OS offline-bundle |
| `RBAC\_Remote\_Operational\_v10.md` | RBAC-design, auth, JWT, MFA, reverse SSH, kommando-whitelist, DB-schema |
| `SABSA\_Architecture\_v10.md` | SABSA enterprise-arkitektur (business attributes, trust boundaries, backup) |
| `TimeLapse\_Security\_Compliance\_v10.md` | Dybdegående security/compliance (STRIDE, DFD, IEC 62443, CRA) |
| `TimeLapse\_Configuration\_Guide\_v10.md` | System- & konfigurationsguide (config-hierarki, edge, video) |
| `TimeLapse\_Edge\_Runbook\_v10.md` | Edge node-runbook (drift, backup, fejlfinding) |
| `TimeLapse\_Roadmap\_v10.md` | Historisk sprint-roadmap (fremadrettet plan i kravregisteret) |
| `System\_Inventory\_v10.md` | Hardware-/pakke-inventar (historisk snapshot; levende data i CMDB) |
| `DOKUMENTPAKKE\_OVERSIGT\_v10.md` | Oversigt + kendte uoverensstemmelser (historik → beslutning) |
| `REGULATORISK\_OG\_STANDARD\_REFERENCE\_v1.md` | Living EU/Danmark horizon scan: AI Act, CRA, NIS2, Data Act, produktansvar, privacy/TV, NIST, ENISA og OT-standarder |
| `SAMARBEJDSMODEL\_PETER\_CLAUDE\_CODEX\_v1.md` | Fælles samarbejds-, review- og handovermodel |


## 3. Levende arbejdsdokumenter (opdateres løbende — ikke versioneret)

| Dokument | Rolle |
| - | - |
| `HANDOVER\_LOG.md` | Løbende session-log — hvad, hvornår, hvorfor |
| `HANDOVER\_Claude\_Codex\_arbejdsdeling.md` | Arbejdsdeling Claude/Codex, åbne tråde, Edge-QA-kontrakt |
| `SERVICES\_OG\_DRIFT\_kilde\_til\_sandhed.md` | Kilde-til-sandhed for services/drift |
| `FAQ\_og\_fejlsøgning.md` | FAQ + fejlsøgning |
| `SYSTEM\_HEALTH\_REGISTER.md` | Health-register |


## 4. Aktuelle design-/analysenotater

`Claude\_Observability\_ITIM\_Design\_2026-06-29.md` (ITIM/observability), `Codex\_Thumbnail\_503\_Analyse\_2026-06-30.md`, `Codex\_Edge\_AI\_NPU\_Modes\_2026-06-28.md` (edge NPU), `Claude\_AI\_Tagging\_Redesign\_2026-06-23.md` (tag-generering), `Nikon\_Z30\_LAB\_Profil\_og\_Fokus\_2026-06-22.md`, `Global\_Config\_og\_Kamera\_Binding\_2026-06-22.md`, `README\_CMDB.md`.

## 5. Reference (fortsat gældende)

`Release\_Promotion\_Methodology\_2026-06-05.md` (styrende release-metodik), `AGGREGATED\_REQUIREMENTS\_UPDATE\_PROVISIONING.md` (detaljeret update/provisioning-sub-register — appendiks til kravregisteret).

## 6. Undermapper

| Mappe | Indhold |
| - | - |
| `Gamle versioner/` | Alle konsoliderede forgængere (base/Claude/Codex-varianter, `.docx`-versionskæder, superseded snapshots). ~74 filer. Kun til historik. |
| `Empiri og kilder/` | Rå kilder: chat-dumps (`Timelaps-chat.docx`, `ChatGpt-input.docx`, `Chat with Gemini.docx`), `Startkrav.docx`, Google Drive-pointere (`.gdoc`/`.gslides`: kravspecifikation, sikkerhedsanalyse v5, præsentation, Nikon Z30 debug m.fl.). |
| `Hardware manualer/` | PDF-manualer: OrangePi 4 Pro (A733), OrangePi PC Plus, OpenClaw-deploy. |
| `Konfig artefakter/` | `fail2ban-\*.conf/.local`, `certbot-renewal.plist`, `cmdb\_models.py`, `security-notes.md`. |


> **Superseded assessment-snapshots** (QA\_Pentest, QA\_SABSA\_Reassessment, VIRTUAL\_PENTEST\_STATUS, SABSA\_RISK\_ANALYSIS\_UPDATE, Sessionoverlevering, Overtagelsesnotat m.fl.) ligger nu i `Gamle versioner/` — deres indhold er foldet ind i `RISK\_ASSESSMENT\_v10.md` og `HANDOVER\_LOG.md`.
