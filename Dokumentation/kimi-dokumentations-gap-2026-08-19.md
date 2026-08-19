# Dokumentations-gap-analyse: dokumentation vs. implementation — og forslag til Hjælp-menu

**Dato:** 2026-08-19
**Forfatter:** Kimi (AI-assistent, review-session)
**Kildegrundlag:** `main` @ `c130fc9`. UI-struktur udledt direkte af `timelapse-ui/src/App.tsx` (alle ruter) og `timelapse-ui/src/components/Navbar.tsx` (menupunkter, roller, tooltips). Dokumentationsdækning verificeret ved gennemgang af overskriftsstruktur og indhold i `Dokumentation/BRUGERMANUAL_v10.md`, `Dokumentation/ADMINISTRATORMANUAL_v10.md`, `Dokumentation/Update_Flow_v10.md`, `Dokumentation/TimeLapse_Edge_Runbook_v10.md`, `Dokumentation/FAQ_og_fejlsøgning.md`, `Dokumentation/DOKUMENTPAKKE_OVERSIGT_v10.md`, `docs/admin-guide.md` og øvrige `docs/`-filer.

---

## 1. Faktisk UI-struktur (sandheden fra koden)

**Topmenu** (alle brugere, nogle kun admin):
`/` Enheder · `/backup` Backup (admin) · `/global-config` Global Config (admin) · `/tags` Tag søgning · `/settings` Indstillinger · `/ai` AI Styring (admin) · `/openwebui` Open WebUI (admin) · `/compliance` Compliance

**Admin-dropdown** (super_admin/admin):
`/system-admin` System Admin · `/local-access` Lokal adgang · `/users` Brugere · `/key-management` Nøgler · `/ssh-tunnel` SSH Tunnels · `/updates` Opdateringer · `/change-tickets` Change tickets · `/post-processing` Post-processing · `/cmdb` CMDB · `/import` Import · `/siem` SIEM · `/retention` Retention · `/redaction` GDPR Sløring · `/observability` Drift

**Sider uden menupunkt** (nås via links/flow): `/devices/:id`, `/sites/:siteId`, `/customers/:customerId`, `/customers/new` (super_admin), `/cameras/:deviceId` (admin), `/lab/:deviceId` (admin), `/devices/:id/timelapse` (admin), `/notifications`, `/login`.

Bemærk: hvert menupunkt har allerede en kort tooltip i Navbar — en god start, men ikke en erstatning for dokumentation.

---

## 2. Implementeret, men ikke (eller kun tyndt) dokumenteret

| Menupunkt / feature | Dokumentationsstatus | Kommentar |
|---|---|---|
| **Lokal adgang** (`/local-access`, PR #77, 2026-08-19) | ❌ Ingen | Helt ny side; live TOTP-kode på `/cameras/:id` er heller ikke dokumenteret. Bør dokumenteres sammen med BT-TOTP-hierarkiet (global/kunde/site/kamera) og auto-sync (PR #71). |
| **Change tickets** (`/change-tickets`) | ⚠️ Tynd | Flowet er beskrevet i `Update_Flow_v10.md` og GO_LIVE, men der findes ingen brugervejledning til selve siden (opret, godkend, SBOM-binding, signering). |
| **SIEM** (`/siem`) | ❌ Ingen brugervejledning | Omtalt i risiko-/compliance-docs, men ingen beskrivelse af siden, filtre, event-typer eller eksport. |
| **GDPR Sløring** (`/redaction`) | ⚠️ Tynd | Beskrevet i DPIA-skabelon og SEC-001; ingen guide til selve siden (kørsl, review af sløringsforslag, tenant-scoping). |
| **Drift** (`/observability`) | ❌ Ingen brugervejledning | Design-doc findes (`Claude_Observability_ITIM_Design_2026-06-29.md`), men ingen manual-tekst om siden. |
| **Import** (`/import`) | ❌ Ingen | 0 omtaler i `docs/admin-guide.md`; brugermanualen nævner ikke import-flowet (TL-IMPORT-virtuelle devices, kunde/site-binding). |
| **Post-processing** (`/post-processing`) | ⚠️ Tynd | Nævnt i manualer, men ingen gennemgang af sidens funktioner (render-options, exposure_ramping-checkbox fra 2026-08-16). |
| **Nøgler** (`/key-management`) | ⚠️ Tynd | Navbar-teksten nævner "API nøgle administration", men siden dækker også key lifecycle (jf. Update_Flow-rapportkommentar). Efter PR #73 er Edge SSH-nøgler public-key-only — det bør fremgå. |
| **System Admin** (`/system-admin`) | ⚠️ Tynd | CMDB-drift-UI og sync-poll-felt nævnt i handover, ikke i manual. |
| **Indstillinger** (`/settings`) og **Notifikationer** (`/notifications`) | ❌ Ingen | Begge ruter eksisterer; ingen dokumentation af hvad brugeren kan indstille/modtage. |
| **Open WebUI** (`/openwebui`) | ⚠️ Uafklaret status | DOKUMENTPAKKE_OVERSIGT markerer "service/rolle uklar" — men Open WebUI-runtime er siden committet (`headend/openwebui_runtime.py`, R27 lukket) og siden er admin-gated. Manualen bør beskrive den reelle drift (launchd, pause/lav-memory-profiler fra 2026-07-20). |
| **AI Styring** (`/ai`) | ⚠️ Tynd | FAQ'en dækker Ollama-vs-Gemini og re-tagning; sidens fulde indhold (modeller & prompts, Normal/Pause/Lav-memory, NPU QA-status) er ikke beskrevet samlet. |
| **Lab-siden** (`/lab/:deviceId`) | ⚠️ Adskilt | `docs/LAB_MODE_TEST_GUIDE.md` findes, men er ikke refereret fra manualerne. |
| **Kamera-siden** (`/cameras/:deviceId`) | ⚠️ Tynd | BT-TOTP QR + live kode, drift-analyse, enhedsidentitet-dropdowns (PR #65) — ingen af delene er i manualerne. |
| **Compliance** (`/compliance`) | ⚠️ Tynd | Brugermanual §7.1 nævner rapport; selve cockpit-siden (inkl. GRC-register-visningen) er ikke beskrevet. |

**Konklusion del 1:** ~8 af 22 menupunkter har reelt ingen brugerdokumentation, og yderligere ~7 er kun tyndt dækket. Manualerne er i dag **opgave-/CLI-orienterede** ("hvordan genstarter jeg headend"), ikke **menu-orienterede** ("hvad kan jeg på denne side, og hvad betyder hvert felt").

---

## 3. Dokumenteret, men forældet eller ikke (længere) implementeret

| Dokument/påstand | Faktisk tilstand | Handling |
|---|---|---|
| `docs/drift-mode-optimering.md` og dele af `docs/system-wide-poll-mechanisms.md` beskriver `heartbeat_interval_minutes`, `config_poll_interval_minutes` som separate loops | Erstattet af én konsolideret sync-poll (`sync_poll_interval_minutes`, PR #76, 2026-08-19). `docs/admin-guide.md` er korrekt opdateret; design-docs er ikke markeret som historiske | Markér de to docs som "historisk design-dokument — se admin-guide.md for aktuel adfærd" |
| `DOKUMENTPAKKE_OVERSIGT_v10.md` "Kendte uoverensstemmelser": Open WebUI "service/rolle uklar" | R27 lukket: `openwebui_runtime.py` committet, UI admin-gated, runtime-styring bygget 2026-07-20 | Opdatér tabellen — konflikten er løst |
| Samme tabel: "Node-agent stoppet — genetabler før go-live" | Status ikke verificeret i denne gennemgang | Verificér og opdatér |
| Samme tabel: "auth-cookie vs localStorage" og "JWT HS256" | Stadig aktuelle (localStorage + HS256 i brug) | Behold som åbne punkter — men flyt dem til GO_LIVE/GRC, så de ikke kun står i en oversigt |
| Ældre docs' `/Volumes/data` (vs. canonical `/Volumes/data-fast`) | Delvist rettet ("data-fast" er canonical) | Reststeder bør fejlsøges ved lejlighed |
| `Update_Flow_v10.md` §Appendiks B API-liste | Formentlig bagud efter PR #44 (exact-SHA deploy), #56/#57 (update lifecycle), #76 (sync-endpoint) | Gennemgå mod `main.py`'s aktuelle ruter |
| Edge Runbook §6 "Reverse SSH-provisioning" | Beskriver ældre provisioning; PR #73 ændrede key-genereringen (Edge ejer nu sine nøgler) | Opdatér §6 med public-key-only-modellen |

**Konklusion del 2:** Hovedparten af forældelse ligger i `docs/`-mappens design-dokumenter (juli 2026) og i oversigtsdokumentets konflikttabel — ikke i v10-manualernes kerne. En lille "historisk"-markering plus opdatering af DOKUMENTPAKKE-tabellen vil fjerne det meste af støjen.

---

## 4. Manualernes tyndhed — konkret forbedringsforslag

Både bruger- og administratormanualen er konsoliderede v10-dokumenter skrevet opgavevist. Det der mangler er en **menu-for-menu, felt-for-felt-beskrivelse**. Forslag til struktur (et kapitel pr. menupunkt):

1. **Formål** — én sætning: hvad løser siden.
2. **Hvem ser den** — rollekrav (viewer/admin/super_admin), direkte fra koden.
3. **Felter og handlinger** — hvert felt, hver knap, hver status: betydning, mulige værdier, konsekvens.
4. **Typiske opgaver** — 2-4 trinvise scenarier.
5. **Fejlfinding** — de 2-3 hyppigste fejl på netop den side, med henvisning til FAQ.
6. **Relateret** — links til bagend-docs (API, GRC, SEC-dokumenter).

Tooltips fra `Navbar.tsx` kan genbruges som udkast til punkt 1 — de er allerede skrevet og reviewet.

---

## 5. Forslag: Hjælp/FAQ/dokumentations-menu i UI'en

**Ja, det bør laves** — og det kan gøres enkelt og holdbart:

### Koncept

Et nyt menupunkt **"Hjælp"** (synligt for alle roller) med:

1. **Kontekstafhængig hjælp:** hver side får et lille "?"-link, der åbner hjælpesektionen for netop den side (anker i hjælpedokumentet). Bygger videre på de eksisterende Navbar-tooltips.
2. **Hjælp-side (`/help`):** renderer de versionsstamped manualer **inde i UI'en** — ingen ekstern dokumentationsserver, virker også på edge-enhedens lokale management-UI uden internet (matcher "edge har ofte ikke internet"-princippet fra GPS-sagen).
3. **FAQ-sektion:** `FAQ_og_fejlsøgning.md` eksisterer allerede og er skrevet i spørgsmål/svar-form — den skal bare exposes i UI'en.
4. **Rolle-filtrering:** admin-ser admin-kapitler; viewer ser kun bruger-kapitler (samme `hasRole`-mekanisme som Navbar).

### Teknisk vej (lav-risiko)

- Manualer konverteres fra de eksisterende Markdown-filer til et bundlet format ved UI-build (fx `vite-plugin-md` eller simpel import af `.md?raw` + en markdown-renderer) — **single source of truth forbliver repoets Markdown**, ingen dublering.
- Hjælpetekster versionsfølger koden: en feature-PR der ændrer en side, skal også opdatere sidens hjælpesektion (kan håndhæves blødt via PR-skabelon-checkliste, ikke CI).
- Alternativ (endnu simplere start): hjælpesiden fetch'er et statisk genereret JSON/HTML-artefakt fra headend, bygget fra `Dokumentation/` ved release — så hjælpen matcher den deployede version, ikke repoets HEAD.

### Hvorfor det passer til projektets principper

- OP-001/Mission Framework: dokumentation som versionsstemplet artefakt der følger koden — modvirker "dokumentation der kun findes i samtaler".
- NIS2/CRA-sporbarhed: operatører kan dokumentere at vejledning fulgte den kørende version.
- GDPR: FAQ/hjælp in-app reducerer risiko for at slørings- og retention-funktioner bruges forkert.

### Anbefalet rækkefølge

1. **Nu:** ret forældelses-punkterne i §3 (små docs-PR'er).
2. **Næste:** skriv menu-for-menu-kapitlerne (§4) for de 8 helt udokumenterede sider — start med Lokal adgang, Import, SIEM, GDPR Sløring.
3. **Derefter:** byg `/help`-siden med kontekstlinks, og surface FAQ'en.
4. **Til sidst:** PR-skabelon-regel "hjælpetekst opdateret?" så dækningen ikke falder bagud igen.

---

## Henvisninger

- `timelapse-ui/src/App.tsx`, `timelapse-ui/src/components/Navbar.tsx` (UI-sandhed)
- `Dokumentation/DOKUMENTPAKKE_OVERSIGT_v10.md` (kendte uoverensstemmelser — delvist forældet tabel)
- `docs/admin-guide.md` (mest opdaterede driftsdoc; korrekt mht. sync-poll)
- `docs/drift-mode-optimering.md`, `docs/system-wide-poll-mechanisms.md` (forældede efter PR #76)
- `Dokumentation/FAQ_og_fejlsøgning.md` (klar til at blive exposed i UI)
- `Dokumentation/kimi-grc-afventer-2026-08-19.md` (samme review-session)
