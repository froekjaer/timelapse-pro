# 00 — START HER (master-indeks & onboarding)

**Formål:** Indgangsdokumentet til TimeLapse Pro-dokumentationen. Læs dette først når du starter en ny session (Claude, Codex eller menneske). Det peger på den seneste, autoritative version af hvert dokument (`*_v10.md`), de levende arbejdsdokumenter og den underliggende empiri.
**Sidst opdateret:** 2026-07-03
**Vedligeholdelsesregel:** Én seneste version pr. dokument, vedligeholdt som `.md`. Ved væsentlig opdatering hæves versionen og forgængeren flyttes til `Gamle versioner/`. Opdatér denne fil når nye autoritative dokumenter kommer til.

---

## 1. Boot en ny session — kernefakta

**Projektprincipper (fra CLAUDE.md):** Senior programmør-niveau. SABSA-ekspert; forstår ISO 27000, IEC 62443, CRA, GDPR. **Dobbelttjek før du udfører.** Ændringer er additive + flag-guardede; ingen skema-brud før live-verifikation; **aldrig hard-delete** (brug quarantine/reversible flyt); rør ikke den andens (Codex') ucommittede arbejde stiltiende.

**Aktuel systemtopologi:**
- **Repo:** `~/projects/timelapse-pro` (= `/Volumes/data-fast/peter-home/projects/timelapse-pro`).
- **Headend (prod):** Mac Mini — FastAPI/uvicorn på `127.0.0.1:8000`, PostgreSQL `timelapse_db`, nginx, UI på `127.0.0.1:5173`, Ollama `127.0.0.1:11434`. Kritiske services kører som system-LaunchDaemons: `dk.froekjaer.timelapse-headend`, `dk.froekjaer.timelapse-postgresql`, `dk.froekjaer.timelapse-nginx`, `dk.froekjaer.timelapse-ui`, `dk.froekjaer.timelapse-wifi-ensure`. Venv `~/.venvs/timelapse-headend`.
- **Storage:** `/Volumes/data-fast` (canonical). Billed-rod = `sftp_base` fra DB-settings (`/Volumes/data-fast/timelapse-incoming/canonical-images`). Backup-target `/Volumes/Backup`.
- **Aktiv edge:** `TL-C87FF9587CA0` (Orange Pi 4 Pro, Nikon Z30). Stale/legacy: `TL-DCA63234D813`.
- **AI-tagging:** Gemini 2.5 Flash (Vertex, europe-west1) + Gemini Batch API (~50% pris); lokal Ollama til tekst/oversættelse. Canonical tags engelsk, danske labels via `ai_tag_vocabulary.display_name_da`.
- **Public (planlagt):** `www.timelapse-pro.dk` (statisk info) + `backend.timelapse-pro.dk` (UI/API bag Cloudflare Tunnel, origin `127.0.0.1:18443`). Lab i dag: `timelapse.froekjaer.dk`.

**Status i én sætning:** LAB/pre-production-klar; **ikke** Internet-facing production-klar. Største blockere: port-/proxy-migration, backup+restore-evidens, GDPR (DPIA/retention/DPA), frisk CMDB/node-agent, MFA + stale credential-cleanup, Nikon Z30 LAB/fokus/video.

---

## 2. Autoritative dokumenter (seneste = v10)

| Dokument | Emne |
|---|---|
| `Timelapse_pro_full_documentation_v10.md` | Samlet systemdokumentation — start her for helheden |
| `RISK_ASSESSMENT_v10.md` | SABSA/ISO/IEC 62443/CRA/NIS2/GDPR risikovurdering + pentest + PKI/Key Mgmt |
| `KRAVREGISTER_og_STATUS_v10.md` | Krav-/ønskeregister, status, tidslinje, oprindelige krav, P0/P1/P2 |
| `GO_LIVE_CHECKLIST_v10.md` | Krav (A–L) før Internet-eksponering + go/no-go |
| `PORT_AUDIT_og_WEBSITE_v10.md` | Portaudit, Cloudflare Tunnel-migration, website/backend-arkitektur |
| `Installationsguide_v10.md` | **Del A: headend-installation · Del B: edge-installation · Del C: edge lokal provisioning** |
| `ADMINISTRATORMANUAL_v10.md` | Drift, sikkerhed, update, backup, CMDB, RBAC, GRC, troubleshooting |
| `BRUGERMANUAL_v10.md` | Bruger/kunde/site manager-manual |
| `Update_Flow_v10.md` | Update-flow: E2E QA, brugermanual, gates, API, OS offline-bundle |
| `RBAC_Remote_Operational_v10.md` | RBAC-design, auth, JWT, MFA, reverse SSH, kommando-whitelist, DB-schema |
| `SABSA_Architecture_v10.md` | SABSA enterprise-arkitektur (business attributes, trust boundaries, backup) |
| `TimeLapse_Security_Compliance_v10.md` | Dybdegående security/compliance (STRIDE, DFD, IEC 62443, CRA) |
| `TimeLapse_Configuration_Guide_v10.md` | System- & konfigurationsguide (config-hierarki, edge, video) |
| `TimeLapse_Edge_Runbook_v10.md` | Edge node-runbook (drift, backup, fejlfinding) |
| `TimeLapse_Roadmap_v10.md` | Historisk sprint-roadmap (fremadrettet plan i kravregisteret) |
| `System_Inventory_v10.md` | Hardware-/pakke-inventar (historisk snapshot; levende data i CMDB) |
| `DOKUMENTPAKKE_OVERSIGT_v10.md` | Oversigt + kendte uoverensstemmelser (historik → beslutning) |

## 3. Levende arbejdsdokumenter (opdateres løbende — ikke versioneret)

| Dokument | Rolle |
|---|---|
| `HANDOVER_LOG.md` | Løbende session-log — hvad, hvornår, hvorfor |
| `HANDOVER_Claude_Codex_arbejdsdeling.md` | Arbejdsdeling Claude/Codex, åbne tråde, Edge-QA-kontrakt |
| `SERVICES_OG_DRIFT_kilde_til_sandhed.md` | Kilde-til-sandhed for services/drift |
| `FAQ_og_fejlsøgning.md` | FAQ + fejlsøgning |
| `SYSTEM_HEALTH_REGISTER.md` | Health-register |

## 4. Aktuelle design-/analysenotater

`Claude_Observability_ITIM_Design_2026-06-29.md` (ITIM/observability), `Codex_Thumbnail_503_Analyse_2026-06-30.md`, `Codex_Edge_AI_NPU_Modes_2026-06-28.md` (edge NPU), `Claude_AI_Tagging_Redesign_2026-06-23.md` (tag-generering), `Nikon_Z30_LAB_Profil_og_Fokus_2026-06-22.md`, `Global_Config_og_Kamera_Binding_2026-06-22.md`, `README_CMDB.md`.

## 5. Reference (fortsat gældende)

`Release_Promotion_Methodology_2026-06-05.md` (styrende release-metodik), `AGGREGATED_REQUIREMENTS_UPDATE_PROVISIONING.md` (detaljeret update/provisioning-sub-register — appendiks til kravregisteret).

## 6. Undermapper

| Mappe | Indhold |
|---|---|
| `Gamle versioner/` | Alle konsoliderede forgængere (base/Claude/Codex-varianter, `.docx`-versionskæder, superseded snapshots). ~74 filer. Kun til historik. |
| `Empiri og kilder/` | Rå kilder: chat-dumps (`Timelaps-chat.docx`, `ChatGpt-input.docx`, `Chat with Gemini.docx`), `Startkrav.docx`, Google Drive-pointere (`.gdoc`/`.gslides`: kravspecifikation, sikkerhedsanalyse v5, præsentation, Nikon Z30 debug m.fl.). |
| `Hardware manualer/` | PDF-manualer: OrangePi 4 Pro (A733), OrangePi PC Plus, OpenClaw-deploy. |
| `Konfig artefakter/` | `fail2ban-*.conf/.local`, `certbot-renewal.plist`, `cmdb_models.py`, `security-notes.md`. |

> **Superseded assessment-snapshots** (QA_Pentest, QA_SABSA_Reassessment, VIRTUAL_PENTEST_STATUS, SABSA_RISK_ANALYSIS_UPDATE, Sessionoverlevering, Overtagelsesnotat m.fl.) ligger nu i `Gamle versioner/` — deres indhold er foldet ind i `RISK_ASSESSMENT_v10.md` og `HANDOVER_LOG.md`.
