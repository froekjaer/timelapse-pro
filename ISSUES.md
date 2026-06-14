# TimeLapse Pro — Issue Register

> Vedligeholdes løbende. Opdateret: 2026-06-14 (session 2)  
> Alvorlighedsgrad: 🔴 Kritisk · 🟠 Vigtig · 🟡 Mindre · ✅ Løst  
> **Git-status:** Seneste commit 2026-06-03 — 59 uncommitted filer pr. 2026-06-14

---

## Indhold
- [A. Sikkerhed](#a-sikkerhed)
- [B. Config & opdateringsflow](#b-config--opdateringsflow)
- [C. Upload- og slot-koordinering](#c-upload--og-slot-koordinering)
- [D. Post-processing](#d-post-processing)
- [E. Software-opdateringssystem](#e-software-opdateringssystem)
- [F. Backend / headend kode](#f-backend--headend-kode)
- [G. Frontend / UI](#g-frontend--ui)
- [H. Edge agent & NPU](#h-edge-agent--npu)
- [I. Tests](#i-tests)
- [J. Infra & deployment](#j-infra--deployment)
- [K. Oprydning & teknisk gæld](#k-oprydning--teknisk-gæld)
- [L. Pre-internet checkliste](#l-pre-internet-checkliste)
- [M. Krav vs. implementeringsstatus](#m-krav-vs-implementeringsstatus)
- [N. Luftgab-arkitektur & opdateringsflow](#n-luftgab-arkitektur--opdateringsflow)

---

## A. Sikkerhed

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| A-01 | 🔴 Åben | Kritisk | **CMDB-endpoints mangler authentication.** Alle CMDB-routes (list, get, update, break-glass checkout) har ingen `require_role`-dependency. Break-glass returnerer klartekst SSH-password til hvem som helst. Der er en TODO-kommentar i koden der anerkender dette. `headend/cmdb.py` |
| A-02 | 🔴 Åben | Kritisk | **Break-glass verificerer ikke caller-identitet.** `admin_username` tages fra request-body og bruges til at returnere password — ingen kobling til autentificeret session. `headend/cmdb.py` linje ~648 |
| A-03 | 🔴 Åben | Kritisk | **`/../../inventory/`-route-hack i CMDB.** Route deklareret som `/../../inventory/{device_id}` under prefix `/api/cmdb` — path-traversal-logik i produktionskode. `headend/cmdb.py` linje ~287 |
| A-04 | 🟠 Åben | Vigtig | **`disable-mfa` mangler rolletjek.** `/api/auth/disable-mfa` kræver kun at man er logget ind — en operator kan deaktivere en andens MFA. `headend/main.py` linje ~800 |
| A-05 | 🟠 Åben | Vigtig | **GPG-check springes over ved manglende signed tags.** `deploy/edge_update.sh` linje ~30: returnerer `0` (godkendt) hvis ingen tags findes — en angriber der kan skrive til `origin/main` kan omgå signaturvalidering. |
| A-06 | 🟡 Åben | Mindre | **`claudetest`-bruger i PostgreSQL skal slettes.** super_admin, mfa off, kodeord `Test1234flow`. `DELETE FROM users WHERE username='claudetest';` (husk `DATABASE_URL=postgresql://...`) |

---

## B. Config & opdateringsflow

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| B-01 | 🔴 Åben | Kritisk | **`config_version` dækker kun device-laget, ikke globale settings.** Hash beregnes kun over `device.device_config`. Ændringer på Global/Kunde/Site-niveau når aldrig ud til edge. Central styring (fx ISO-parametre) virker ikke. Fix: hash hele den udleverede `cfg` kanonisk i `get_config`. Forudsætter B-02 løst først. `headend/main.py` linje ~2272 |
| B-02 | 🟠 Åben | Vigtig | **Rapport-data (`camera_params`, `camera_profile`, `wifi_data`) ligger i `device_config` og sendes til edge.** `camera_params` alene er 115 KB — edge læser dem aldrig (grep bekræftet). Forurener config_version-hashen og spælder ~35 MB/døgn på mobilforbindelser. Fix: udelad disse felter fra det der sendes til edge og fra hash-beregningen. Arkitektonisk løsning: flyt dem til separat felt/tabel. |
| B-03 | 🟠 Åben | Vigtig | **"Send kun ved ændring" er ikke implementeret.** Edge sender ingen `If-None-Match`-header, headend returnerer altid hele 121 KB config. Fix: headend beregner hash tidligt, returnerer `304 Not Modified` hvis uændret. Edge's `_get()` behandler allerede alt der ikke er 200 som "behold config" — 304-understøttelse virker med det samme, log-feedback kan poleres separat. Bygger på B-01 + B-02. |
| B-04 | 🟠 Åben | Vigtig | **UI-toggle til upload-slot-settings + settings-bump.** `PUT /api/admin/settings` (`update_settings`) bumper ikke `config_version` → ændringer i settings når ikke ud til edge. Mangler også UI-felt til slot-konfiguration. |

---

## C. Upload- og slot-koordinering

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| C-01 | 🟠 Åben | Vigtig | **Slot-kontrol er designet men slået fra (`upload_slot_enforced=false`).** Mekanismen er fuldt implementeret — deterministisk per-device vindue, køholdbar lokal buffer. Aktivering kræver at B-01 er løst (ellers når `enforced=true` aldrig ud til edge). |
| C-02 | 🟠 Åben | Vigtig | **Backup går udenom slot-mekanismen.** `agent.py` linje ~987 (`upload_edge_backup`) tjekker ikke slot. Heartbeat er undtaget med vilje (liveness skal være fri). Capture er allerede koblet på slot. |
| C-03 | 🟠 Åben | Vigtig | **Slot skal udvides til downloads** (artefakter, OS-bundles, apt-debs). Video får separat kanal. Design-overvejelse påkrævet: en enhed der venter på en sikkerhedsopdatering må ikke blokeres af upload-vinduet — separate kvoter for kritiske downloads. |
| C-04 | 🟡 Åben | Mindre | **nginx mangler eksplicit `proxy_read_timeout` på `/api/`-blokken.** Arver default 60s. openwebui-blokken har 3600s (linje 90-91, 115-116). Med slot-kontrol aktiveret opstår byge-problemet ikke, men 120s som sikkerhedsnet er fornuftigt. |
| C-05 | ✅ Løst | — | **Edge-upload returnerede HTTP 500.** Nginx temp-mapper ejet af `nobody` (levn fra `sudo nginx`). Løst ved at stoppe nginx, slette temp-mapper, genstarte som `peter`. Verificeret 13. juni 2026. **Regel fremover: brug altid `brew services` eller `nginx -s reload`, aldrig `sudo nginx`.** |

---

## D. Post-processing

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| D-01 | 🔴 Åben | Kritisk | **Thumbnail-genoprettelse kører ikke.** Post-processing identificerer billeder med manglende thumbnails men genererer dem ikke. Mangler: kald til thumbnail-generator for fundne billeder + markering af status efterfølgende. |
| D-02 | 🔴 Åben | Kritisk | **AI-tag genoprettelse kører ikke.** Post-processing identificerer billeder uden AI-tags men sender dem ikke gennem AI-pipeline'n. Mangler: kald til `ollama_service` / `integration.py` worker for fundne billeder + re-queue-logik. |
| D-03 | 🟠 Åben | Vigtig | **AI-tags er ikke meningsfulde nok.** De genererede tags er for generiske og giver begrænset søgeværdi. Skal undersøges: prompt til `llava-phi3`, kategorisering, hvilke tags der faktisk er nyttige for byggeplads-kontekst (vejr, aktivitet, maskiner, personale, fremgang). Kræver prompt-tuning + evt. struktureret tag-skema. |
| D-04 | 🟡 Åben | Mindre | **`Capture.filesize_mb` i TypeScript-types matcher ikke backend.** `types/index.ts` linje ~34: `filesize_mb: number | null`, men database-model gemmer `filesize` (bytes, integer). Kan give null-visning i UI. |

---

## E. Software-opdateringssystem

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| E-01 | 🟠 Åben | Vigtig | **`build_os_bundle.py` mangler / er ikke kørt.** 142 sikkerhedsopt. + 62 funktionelle OS-opdateringer står korrekt `blocked` i databasen og afventer bundle-bygning. Bundler skal bygges i lab, signeres og publiceres som artefakter. |
| E-02 | 🟠 Åben | Vigtig | **Hele opdateringsflowet er bevist i trin 1–3, men trin 4+ (bundle-download → edge-install) er ikke implementeret/testet end-to-end.** Edge rapporterer installed-state korrekt, og headend reconciler korrekt. Men selve distributionstrinnet (download signeret bundle → edge verificerer → apt-install) mangler. |
| E-03 | 🟡 Åben | Mindre | **Sprint C fix-scripts (`sprint_c/*.py`) ligger stadig i repo.** Er allerede kørt og integreret — udgør rod og risiko for at blive kørt igen ved en fejl. Bør flyttes til `Dokumentation/historik/` eller slettes. |

---

## F. Backend / headend kode

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| F-01 | ✅ Løst | Kritisk | **Sprint C v3-migration kører aldrig.** `new_cols_v3`-blokken (MFA/SFTP-kolonner til `customers` og `sites`) var indrykket i `except`-blok → kørte kun ved fejl. Rettet 2026-06-14: blokken er nu et selvstændigt `try/except` på korrekt indrykning. |
| F-02 | 🔴 Åben | Kritisk | **Duplikeret `DELETE /api/admin/users/{user_id}`** med forskellig sikkerhedslogik. Linje ~1067 mangler self-delete-guard, linje ~10565 har den. FastAPI bruger linje 1067. |
| F-03 | 🟠 Åben | Vigtig | **Kreativ engine-initialisering** — `engine = next(iter([].__class__.mro())) if False else __import__('database').engine`. I praksis altid `__import__('database').engine`, men ulæsbar og skrøbelig. `headend/main.py` linje ~177 |
| F-04 | 🟠 Åben | Vigtig | **`ConfigDefaults.session_policy`-kolonne mangler** i databasemodellen (database.py), men koden bruger den flere steder (main.py linje ~512, 912, 9079, 9095). Kan give AttributeError. |
| F-05 | 🟠 Åben | Vigtig | **Duplikeret `ensure_utc`** — tre separate definitioner: `main.py` linje ~96, `database.py` linje ~544, `database.py` linje ~705. Python bruger den seneste definition, men det er klart teknisk gæld. |
| F-06 | 🟠 Åben | Vigtig | **SQLite er stadig default i `database.py`.** `DATABASE_URL` defaulter til `sqlite:///./timelapse_headend.db`. En forkert miljøkonfiguration kører stille på SQLite i stedet for at fejle klart. **Bemærk: `DATABASE_URL` er sat i plist, ikke i shell-env — sæt altid `DATABASE_URL=postgresql://timelapse@localhost/timelapse_db` foran scripts der køres fra shell.** |
| F-07 | 🟡 Åben | Mindre | **`CaptureRequest`-model har `sha256_pre_xmp` deklareret to gange** (linje ~281 og ~305). Python bruger den seneste, linje 281 ignoreres. |
| F-08 | 🟡 Åben | Mindre | **`@app.on_event("startup")` defineret to gange.** FastAPI understøtter teknisk set flere handlere, men rækkefølgen er ikke garanteret og logikken er spredt. |
| F-09 | 🟡 Åben | Mindre | **`apply_*.py` patch-scripts i `headend/ai/`.** Samme mønster som sprint_c: allerede kørt, men stadig i mappen. Kan fejlagtigt køres igen. |

---

## G. Frontend / UI

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| G-01 | 🔴 Åben | Kritisk | **`AuthContext.tsx`: race condition ved opstart.** Brugerinfo læses fra `localStorage` og sættes straks som autentificeret, derefter verificeres cookie asynkront. I vinduet mellem mount og API-svar er brugeren tilsyneladende logget ind med en potentielt udløbet cookie. |
| G-02 | 🟠 Åben | Vigtig | **`token`-state i `AuthContext` er dead code.** Artefakt fra gammel JWT Bearer-løsning — `token` sættes aldrig, men `setToken(null)` kaldes stadig ved logout. `api/client.ts` bruger korrekt `withCredentials: true` (cookies). Bør fjernes for at undgå forvirring. |
| G-03 | 🟠 Åben | Vigtig | **Dobbelt navigation i WebAuthn-login.** `LoginPage.tsx` linje ~91: både `navigate(from, { replace: true })` og `window.location.href = from`. Den hårde redirect overstyrer React Router. |
| G-04 | 🟠 Åben | Vigtig | **UI-toggle til slot-konfiguration mangler.** `upload_slot_enforced`, `upload_slot_cycle_seconds` etc. er ikke eksponeret i UI. Nødvendigt for at aktivere C-01. |
| G-05 | 🟡 Åben | Mindre | **`mfa_token`-flow er skrøbeligt.** `AuthContext` login() returnerer `mfa_token` fra `data.mfa_token` — fungerer, men er unødigt indirekte og svær at fejlfinde. |
| G-06 | 🟠 Åben | Vigtig | **Admin-menu til genstart af services og reboot mangler.** Der skal tilføjes en sektion i Admin-UI (SystemAdminPage eller dedikeret side) med: genstart af edge-services pr. device (timelapse-capture, timelapse-agent, timelapse-tunnel), genstart af headend-services (uvicorn, nginx), reboot af edge-device og reboot af headend (Mac Mini). Kræver: nye API-endpoints der udsteder systemd-kommandoer via SSH-tunnel (edge) eller lokalt (headend), bekræftelsesdialog i UI, og audit-log af handlingen. |

---

## H. Edge agent & NPU

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| H-01 | 🟠 Åben | Vigtig | **`SshTunnelManager` modtager `ConfigManager`-objekt, ikke `dict`.** `sprint_c/fix_sprint_c_agent.py` linje ~43: `self._tunnel = SshTunnelManager(self._cfg, self._api)` — men `SshTunnelManager.__init__` (`ssh_manager.py` linje ~68) forventer `config: dict`. Tunnel fejler ved første brug. |
| H-02 | 🟡 Åben | Mindre | **`ssh_manager.py` eksisterer to steder.** `sprint_c/ssh_manager.py` og `edge/tunnel/ssh_manager.py` (kopieret af fix-script). Uklart hvilken der er master — ændringer synkroniseres ikke. |
| H-03 | 🟠 Åben | Vigtig | **Lokal NPU-baseret billedkvalitetskontrol mangler.** Orange Pi 4 Pro (RK3588S) har NPU der kan køre et lille ONNX/RKNN-model lokalt — skal bruges til at analysere hvert billede _inden_ upload for: fokus/skarphed, kondensation/dug/sne/snavs på linse eller kameraplast, væsentlig ændring i billedvinkel. Resultatet skal: (1) tagge billedet lokalt, (2) notificere headend via heartbeat/SIEM-event, (3) evt. udløse power-cycle eller alarm. Forudsætter valg af model (MobileNet/RKNN), kvantisering til NPU og integration i capture-pipeline. Se også D-03 (AI-tag kvalitet på headend). |
| H-04 | 🔴 Åben | Kritisk | **Oprettelse og klargøring af ny edge-enhed er ikke dokumenteret som fungerende flow.** Captive portal/AP-mode mangler (krav A-31). Zero-touch provisioning er delvist implementeret men ikke testet end-to-end. Mangler: trin-for-trin runbook der kan følges uden netværk, engangsbrug bootstrap-token, og verificeret smoke-test efter provisioning. `Dokumentation/Edge_Local_Provisioning_Runbook_2026-06-03.md` dækker designet men ikke et testet flow. |

---

## I. Tests

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| I-01 | 🟠 Åben | Vigtig | **Tests er grep-checks, ikke rigtige tests.** `test_headend_endpoints.py` checker blot om string-literals eksisterer i `main.py` som tekstfil. Tester ikke at endpoints er registreret, returnerer korrekte statuskoder, validerer auth eller interagerer med DB. |
| I-02 | 🟡 Åben | Mindre | **`test_no_duplicate_imports` er ufuldstændig.** Finder kun `import X`-duplikater, ikke `from X import Y`-duplikater. |

---

## J. Infra & deployment

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| J-01 | 🟠 Åben | Vigtig | **uvicorn kører som én process uden workers.** Plist: `uvicorn main:app --host 0.0.0.0 --port 8000`, kører som root. Synkron `out.write(chunk)` i upload-handlers blokerer event-loop kortvarigt. Med slot-kontrol reduceres problemet, men `run_in_threadpool` for disk-I/O er den rene løsning. |
| J-02 | 🟡 Åben | Mindre | **Lock-fil i `edge_update.sh` ryddes ikke ved SIGKILL.** `trap "rm -f $LOCK_FILE" EXIT` virker ikke ved SIGKILL → stale lock-fil kan blokere fremtidige opdateringer. |
| J-03 | ✅ Løst | — | **Parallelt CMDB-system fjernet.** Et fejlagtigt bygget parallelt CMDB-system (`headend/cmdb/`-dir + `cmdb_models.py`) blev fjernet kirurgisk. Peters `headend/cmdb.py` er det autoritative. |

---

## K. Oprydning & teknisk gæld

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| K-01 | 🟠 Åben | Vigtig | **`.bak`-filer i repo.** `headend/main.py.bak_*` (6 stk.), `timelapse-ui/src/App.tsx.bak_*`, `timelapse-ui/src/pages/DevicePage.tsx.bak_*` (4 stk.) m.fl. Bør ikke committes — tilføj `*.bak_*` til `.gitignore` og slet eksisterende. |
| K-02 | 🟡 Åben | Mindre | **Personlige kommentarer i produktion.** `main.py` linje ~176: `#Peter        from sqlalchemy import text`, linje ~8656: `#Peter import subprocess as _subprocess`. Bør ryddes op. |
| K-03 | 🟡 Åben | Mindre | **Sprint C fix-scripts (`sprint_c/*.py`) skal flyttes/slettes** efter verifikation. Se E-03. |
| K-04 | 🟡 Åben | Mindre | **`secrets/gcp-service-account.json` i repo.** Credentials-fil ligger i projektmappen. Bør ligge i `.gitignore` og ikke committes. |

---

## L. Pre-internet checkliste

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| L-01 | 🟡 Åben | — | **nginx flyttes fra 80/443 → 18443.** Router forwarder public:10443 → Mac:18443. Frigør 80/443/21/22 til CrushFTP. |
| L-02 | 🟡 Åben | — | **Nyt certifikat til `timelapse-api.froekjaer.dk`.** Nuværende cert dækker `timelapse.froekjaer.dk` + `openwebui.froekjaer.dk`. |
| L-03 | 🟡 Åben | — | **CrushFTP installeres og konfigureres** på 80/443/21/22. Kører ikke endnu. |
| L-04 | 🟡 Åben | — | **Go/no-go assessment** — gennemfør alle kritiske og vigtige issues ovenfor inden maskinen åbnes mod nettet. |

---

## K. Oprydning & teknisk gæld — tilføjelse

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| K-05 | 🔴 Åben | Kritisk | **Git-backlog: 59 uncommitted filer, seneste commit 2026-06-03.** 11 dages arbejde (Codex + lokal) er ikke committet. Inkl. ændringer til `edge/agent.py`, `headend/main.py`, `headend/cmdb.py`, `headend/ai/`, `timelapse-ui/src/` m.fl. Risiko for tab af arbejde. Bør committes straks i logiske enheder med GPG-signering. |

---

## M. Krav vs. implementeringsstatus

Baseret på gennemgang af al dokumentation (AGGREGATED_REQUIREMENTS, RISK_ASSESSMENT_v6, Codex_Overtagelsesnotat, Update_Flow_Guide, Release_Promotion_Methodology, Edge_Local_Provisioning_Runbook, SYSTEM_HEALTH_REGISTER, SourceCode_Inventory — alle per 2026-06-03/05).

**Samlet status (verificeret mod kode):** 26 krav ✅ · 28 krav 🔶 delvist · 20 krav ❌ mangler · 1 ❓ ukendt

### M-A. Funktionelle krav

| ID | Status | Krav |
|----|--------|------|
| M-A01 | ✅ | Multi-kamera burst capture med threading (`edge/camera/drivers/`) |
| M-A02 | ✅ | Driver-abstraktionslag med registry — nyt kamera tilsluttes uden kerne-ændring |
| M-A03 | ✅ | Stabil USB-symlink kameraidentifikation via udev (`/dev/timelapse-camN`) |
| M-A04 | ✅ | Logisk kamera adskilt fra fysisk hardware (Camera + DeviceAssignment i DB) |
| M-A05 | 🔶 | Nikon Z30 som primært mål — remote focus/liveview/power stability ikke fuldt stabilt |
| M-A06 | ✅ | Billedkvalitetskontrol med fallback (`edge/capture/quality.py`) |
| M-A07 | ✅ | Relay-styring til kamerastrøm (`edge/camera/relay.py`) |
| M-A08 | ✅ | Store-and-forward med 50 GB cirkulær lokalbuffer |
| M-A09 | ✅ | API-primær upload + SFTP som backup-kanal |
| M-A10 | ✅ | SHA-256 integritetshash + XMP-sidecar pr. billede |
| M-A11 | ✅ | Nightly reboot og suspend mellem captures |
| M-A12 | ✅ | Multi-tenant hierarki global → kunde → site → device med RBAC |
| M-A13 | ✅ | RBAC med roller: super_admin, admin, customer_approver, viewer |
| M-A14 | ✅ | SFTP chroot-isolation pr. site/kunde |
| M-A15 | ✅ | Reverse SSH tunnel til remote management med deny-flag |
| M-A16 | ✅ | SSH tunnel UI (`SshTunnelPage.tsx`) |
| M-A17 | 🔶 | CMDB: Edge rapporterer installed-state — mangler `device_type`, credential-status, dummy-klassifikation |
| M-A18 | 🔶 | Headend reconciler til update-katalog — fungerer men UI-import mangler, primært CLI |
| M-A19 | 🔶 | Update-policy pr. device — hierarkisk håndhævelse ikke fuldt realiseret i UI/DB |
| M-A20 | 🔶 | Staged rollout global→kunde→site→device — UI dækker kun global/device, kamera-scope mangler |
| M-A21 | 🔶 | Change ticket oprettelse og godkendelse — mangler rollback-plan, artifact-reference, maintenance window |
| M-A22 | ✅ | Signerede change tickets og artifact-manifester — `_sign_payload()` bruges konsekvent; `signature`, `signed_by`, `signed_payload_sha256` på tickets, approvals, artifacts og manifests (`main.py:4074, 6108, 6438`) |
| M-A23 | 🔶 | Headend-mediated update, artifact download og offline dpkg-bundle install — designet, ikke live-tested |
| M-A24 | ✅ | Per-target deployment status — `edge/agent.py:1319-1328` `_report_update()` POSTer status tilbage med `update_id`, `status`, `device_id`; headend tracker `deployed_count`/`failed_count` i `PendingUpdate` |
| M-A25 | 🔶 | Automatisk rollback ved fejlet update — stub eksisterer, Headend-binding er ufærdig |
| M-A26 | 🔶 | Force rollback fra UI — endpoint eksisterer, per-target tracking mangler |
| M-A27 | ❌ | **Release-kanaler: candidate→lab_ready→lab_deployed→lab_accepted→prod** — ikke implementeret i datamodel/UI |
| M-A28 | ❌ | **LAB acceptance gate med smoke tests og rollback evidence** — ikke implementeret |
| M-A29 | 🔶 | UI: Release lab, Release registry, Production approvals, Deployment cockpit — deles dækkes af /updates og /change-tickets |
| M-A30 | 🔶 | Edge bootstrap/zero-touch provisioning — `/api/bootstrap` eksisterer, production-grade lifecycle ufærdig |
| M-A31 | ❌ | **Captive portal / AP-mode til lokal netværksopsætning** — designet, ikke implementeret |
| M-A32 | 🔶 | Key Management UI — siden eksisterer, intern CA med revokering er ufærdig |
| M-A33 | 🔶 | Headend Backup og restore — backup til NAS eksisterer, automatisk off-site og testbar restore mangler |
| M-A34 | 🔶 | AI/Ollama integration til billedanalyse og tagging — modul eksisterer, kapacitetspolitik mangler |
| M-A35 | 🔶 | SIEM/syslog modtagelse og visning — eksisterer, fuldstændig pipeline ukendt |
| M-A36 | ❓ | Timelapse-video generering — UI-side eksisterer, backend-implementering ikke verificeret |
| M-A37 | 🔶 | Compliance-rapport generator — CompliancePage eksisterer, fuld automatisk compliance-pakke mangler |
| M-A38 | 🔶 | Notifications og alarmhåndtering — alarm_engine + notify eksisterer |
| M-A39 | 🔶 | Konfigurationshierarki administrerbart fra UI — eksisterer, effective-config visning ikke fuldt realiseret |
| M-A40 | 🔶 | Import af eksisterende data — importer.py + ImportPage eksisterer, CMDB-klassifikation åbent punkt |
| M-A41 | ❌ | **Admin-menu til genstart af services og reboot** — se G-06 |
| M-A42 | ❌ | **Lokal NPU AI på edge til billedkvalitetskontrol** — se H-03 |

### M-B. Non-funktionelle krav

| ID | Status | Krav |
|----|--------|------|
| M-B01 | ✅ | HttpOnly cookie-session + JWT med 12t udløb |
| M-B02 | ✅ | TOTP + WebAuthn MFA til UI-login — `pyotp`, `py_webauthn`, `setup_mfa`, `confirm_mfa` i `main.py:763-840`; WebAuthn register/login flow `main.py:574-733`; MFA step-up UI i `LoginPage.tsx` og `UsersPage.tsx` |
| M-B03 | ❌ | **MFA-gating ved high-risk godkendelser** — MFA-gate gælder kun OpenWebUI-adgang (`main.py:10828`), ikke `approve_change_ticket` (`main.py:6418`) eller backup/restore endpoints |
| M-B04 | 🔶 | Fail-fast ved manglende JWT_SECRET i production — mitigeret, men HLTH-010 stadig åben |
| M-B05 | ❌ | **Intern CA med device client certs (mTLS)** — planlagt Sprint D, intet fund i kodebasen |
| M-B06 | ✅ | SSH host-key trust: ingen AutoAddPolicy i production |
| M-B07 | ✅ | WiFi-passwords håndteres ikke via Headend i production |
| M-B08 | 🔶 | Secrets ikke i Git — `secrets/gcp-service-account.json` utracked, `headend/exports/` ukorrekt ignoreret |
| M-B09 | ❌ | **Disk-kryptering på Edge (LUKS)** — intet fund for `luks`/`cryptsetup` i `edge/` |
| M-B10 | ❌ | **CA-pinning og cert-fingerprint i bootstrap.yaml** — planlagt Sprint D/E |
| M-B11 | 🔶 | Artifacts signeret og verificeret — sha256-verifikation i `_run_artifact_app_update()`, men signer-infrastruktur ikke fuldt produktionssikret |
| M-B12 | 🔶 | Legacy git-update path er opt-in — gjort opt-in via env-flag, kode eksisterer stadig |
| M-B13 | ✅ | Edge autonom drift under netværks-/Headend-udfald |
| M-B14 | ❌ | **Atomisk symlink-aktivering** — artifact-update bruger `shutil.copy2` + backup/prev, ikke atomisk symlink-swap til `/opt/timelapse/current` |
| M-B15 | ❌ | **Maintenance window håndhæves af Edge** — felt eksisterer i `ChangeTicket`-model, men `edge/agent.py` checker det aldrig |
| M-B16 | ❌ | **Failure threshold: rollout stopper automatisk ved fejlgrænse** — intet fund |
| M-B17 | ❌ | **Frontend lint** — `npm run lint` fejler med **205 errors, 9 warnings** (primært `@typescript-eslint/no-explicit-any`) |
| M-B18 | 🔶 | Python testmiljø — `pytest` tilgængeligt, `tests/` eksisterer, integration-tests kræver live headend på `192.168.86.132` |
| M-B19 | ❌ | **Tests er funktionelle** — eksisterende tests er primært string-presence checks |
| M-B20 | 🔶 | Vite bundle-størrelse — ~1020 kB minified, Vite advarer om overskredet grænse |
| M-B21 | 🔶 | Komplet audit trail — `approved_by/at` + `signed_by` + `signed_payload_sha256` eksisterer; MFA-kontekst i audit mangler |
| M-B22 | 🔶 | Tenant-isoleret audit eksporterbar — RBAC-scope eksisterer, systematisk kunde-eksport mangler |
| M-B23 | ✅ | SBOM genereres — `cmdb.py:135-162` genererer CycloneDX SBOM runtime fra CMDB inventory; endpoints `/api/cmdb/{device_id}/sbom` og `/sbom/all`; `sbom_ref` felt på artifacts og change tickets |
| M-B24 | ❌ | **VDP/security.txt, DPIA og NIS2 incident-process** — CRA nævnes kun som label, ingen `security.txt` fil eller endpoint |
| M-B25 | ❌ | **Supportperiode-policy og CRA/CE-plan** — mangler |
| M-B26 | 🔶 | ISO 27001 — kortlagt i krav, ikke fuldt operationaliseret |
| M-B27 | 🔶 | NIS2 supply chain — risikovurdering eksisterer, ikke formelt godkendt |
| M-B28 | 🔶 | IEC 62443 — RBAC dækker dele, intern CA mangler |
| M-B29 | ✅ | GDPR: tenant-isolation, least access og kundekontrol (SFTP chroot + RBAC) |
| M-B30 | 🔶 | CMDB-fuldstændighed — `device_type`, credential-status, dummy-klassifikation mangler |
| M-B31 | 🔶 | Pre-flight — `preflight`-fase eksisterer i update-status, men ingen port-register eller konflikt-check |
| M-B32 | ❌ | **Co-resident software klassificeret: TLP-managed/TLP-platform/Foreign** — intet fund |
| M-B33 | ❌ | **README projekt-specifik** — er stadig default Vite-template tekst |
| M-B34 | 🔶 | Device-identity — MAC-afledt `device_id` bruges i dag, cert-baseret planlagt Sprint D |
| M-B35 | ✅ | Bootstrap token engangsbrug — `used_at`, `expires_at`, `revoked` alle implementeret og håndhævet (`main.py:1097-1106`, `database.py:480`, `revoke_bootstrap_token` endpoint) |
| M-B36 | ❌ | **RTO/RPO dokumenteret** — nævnt som krav i docs, ingen faktiske værdier defineret |
| M-B37 | ❌ | **Restore-test udføres og dokumenteres som evidence** |
| M-B38 | 🔶 | OS offline artifact-builder (`build_os_bundle.py`) — implementeret 2026-06-08, live test mangler |
| M-B39 | ✅ | Artifact-baseret Headend-update — `_update_requires_headend_artifact()` + `_run_artifact_app_update()` med sha256-verifikation; ingen ukontrolleret git pull |

---

## N. Luftgab-arkitektur & opdateringsflow

> **Arkitekturafgørelse (2026-06-14):** Hverken edge eller produktion-headend kan forventes at have direkte internetadgang. Al software, opdateringer og tidssynkronisering skal gå via headend. Lab-headend er den eneste node med internetadgang.

| ID | Status | Prioritet | Beskrivelse |
|----|--------|-----------|-------------|
| N-01 | ✅ Løst | Kritisk | **Headend som apt-proxy/mirror.** Implementeret 2026-06-14: `headend/tools/fetch_os_bundle.py` downloader `.deb`-filer fra Ubuntu mirrors via HTTP (ingen apt-get). Producerer identisk bundle-format som `build_os_bundle.py`. Konfigurérbar suite/arch. Registreres via eksisterende `catalog-os-bundle` endpoint. |
| N-02 | ✅ Løst | Kritisk | **NTP via headend.** Implementeret 2026-06-14: `_sync_time_from_headend()` i `edge/agent.py` læser `server_time` fra heartbeat-svar og sætter systemtid (`date -s`) hvis drift > 5 sek. Skriver til hardware clock med `hwclock --systohc`. Kræver at edge-agenten kører som root (er tilfældet i prod). |
| N-03 | ✅ Løst | Kritisk | **TimeLapse Pro artifact-bygning — fase 1: GitHub tag poller.** Implementeret 2026-06-14: `_git_tag_poller_loop()` starter ved headend-opstart, poller hvert 1t (konfigurérbart via `TIMELAPSE_GIT_TAG_POLL_INTERVAL_HOURS`), verificerer GPG-signatur, bygger artifact via `git archive` uden at ændre working tree. Ny endpoint `POST /api/updates/artifacts/catalog-from-git-tag` til manuel trigring. Seed af already-seen tags fra DB ved start. |
| N-04 | 🟠 Åben | Vigtig | **Prod-headend OS/dependency-opdateringer.** Prod-headend har internetadgang og kan nå Ubuntu mirrors og Homebrew CDN. Nuværende `_sync_managed_application_updates()` (Homebrew-allowlist) kan fungere direkte. OS-bundle til edge: prod-headend downloader `.deb`-filer fra Ubuntu mirrors, bundterer offline artifact, serverer til edge via eksisterende artifact-flow. Ingen air-gap-problematik i fase 1. |
| N-05 | ✅ Løst | Vigtig | **Inventory-rapportering periodisk.** Implementeret 2026-06-14: `_report_inventory()` i `edge/agent.py` kalder sig selv fra heartbeat-loopen, rapporterer hvis `inventory_report_interval_hours` (default 23) er gået siden sidst. `_last_inventory` state variabel sporer seneste rapport. Force=True ved opstart. |
| N-06 | 🟠 Åben | Vigtig | **Automatisk reconcile — ingen manuel indgriben.** I dag kræves at admin manuelt kører reconcile eller importerer apt-list. Mangler: periodisk (nattligt?) job på lab-headend der: (1) checker ny apt-liste mod upstream (via lab's internet), (2) sammenligner mod CMDB for alle devices, (3) opretter `PendingUpdate`-rækker automatisk, (4) notificerer admin om nye sikkerhedsopdateringer. |
| N-07 | 🟡 Åben | Mindre | **DNS for edge.** Hvis edge ikke kan nå internet, skal DNS-opslag for headend-domænet løses lokalt (via router/DHCP eller statisk `/etc/hosts`). Verificér at edge ikke er afhængig af ekstern DNS for at nå headend. |

---

## Prioriteret rækkefølge (foreslået)

**Omgående (sikkerhed):**
1. A-01/A-02/A-03 — CMDB authentication + route-hack
2. A-04 — `disable-mfa` rolletjek
3. A-06 — slet `claudetest`-bruger

**Derefter (config-flow, forudsætning for næsten alt andet):**
4. B-02 — rens rapport-data fra edge-config
5. B-01 — hash hele cfg i `get_config`
6. B-03 — implementér HTTP 304
7. B-04 — UI-toggle + settings-bump

**Parallelt kan løses:**
8. ~~F-01 — fix migration-indrykning (Sprint C v3)~~ ✅ Løst 2026-06-14
9. F-02 — fjern duplikeret DELETE-endpoint
10. G-01 — fix AuthContext race condition
11. D-01 — afklar og implementér post-processing rettelser
12. ~~E-01/E-02 — build_os_bundle~~ ✅ N-01/N-02/N-03/N-05 løst 2026-06-14

**Til sidst:**
13. C-01/C-02/C-03 — aktivér slot-kontrol + udvid til backup/downloads
14. L-01→L-04 — pre-internet checkliste
