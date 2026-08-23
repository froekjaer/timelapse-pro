# TimeLapse Pro — Menuguide: Admin (v1)

**Dato:** 2026-08-20
**Formål:** Menu-for-menu beskrivelse af alle punkter i **Admin-dropdown'en** samt de admin-gatede sider uden menupunkt (Kamera-siden, Lab). Supplerer `ADMINISTRATORMANUAL_v10.md`, som er opgave-/CLI-orienteret; denne guide beskriver selve UI-siderne felt for felt.
**Kilde:** Udledt direkte af koden (`timelapse-ui/src/pages/`, `Navbar.tsx`) på `main @ c130fc9` — beskrivelserne matcher den faktiske UI.
**Roller:** Alle sider i denne guide kræver `admin` eller `super_admin` (Brugere kræver `super_admin`).

---

## Topmenu (admin-delen)

### Backup (`/backup`) — "Drift & Resilience"

- **Formål:** Backup-scheduling, overvågning af backup-jobs, restore-readiness og edge-klargøring (onboarding).
- **Sektioner:**
  - *Headend disaster recovery* — plan og status for headend-backup.
  - *Off-host target* — destinationssti for backup uden for værten (fx `/Volumes/backup/timelapse`).
  - *Edge backup og restore readiness* — pr. enhed: er backup sat op, og kan der restores?
  - *Klargør ny Edge* — opret klargøringspakke til en ny enhed (enheds-ID som `tl-kamera1-a3f2`, headend-URL, Wi-Fi SSID/adgangskode, landekode, installationsnote). Inkluderer *ISO pipeline status*.
- **Typiske opgaver:**
  1. Kør backup nu og verificér derefter med `verify_backup.sh --test-restore` (se ADMINISTRATORMANUAL §8.2) — go-live-krævet E-02 er netop en dokumenteret restore-test.
  2. Klargør ny enhed: udfyld formularen → hent pakke → følg `INSTALLATIONSMANUAL_EDGE_GENERATOR_v1.md`.
- **Fejlfinding:** Backup der er ældre end 48 timer udløser advarsel (standard `--max-age 48`).

### Global Config (`/global-config`)

- **Formål:** Hierarkisk konfiguration: Global → Kunde → Site → Kamera, med arv og overrides for alle parametre.
- **Sektioner:** *Arv og overrides* — hvert felt viser den effektive værdi og om den er arvet ("Arv"-placeholder = tomt felt betyder arv fra overliggende lag). Herunder også sync-poll-intervallet (`sync_poll_interval_minutes`, standard 5 min) som styrer hvor ofte enheder henter config, rapporterer heartbeat og sender SIEM-events i én samlet poll.
- **Regel:** Sæt kun overrides på det laveste lag der reelt skal afvige — ellers bliver fremtidige globale ændringer blokeret for dén enhed.
- **Relateret:** `Global_Config_og_Kamera_Binding_2026-06-22.md`, `docs/admin-guide.md` §Global Config.

### AI Styring (`/ai`)

- **Formål:** Kontrol af AI-billedanalyse: modeller, prompts, driftstilstand og tag-kvalitet.
- **Sektioner:**
  - *Ollama memory-styring* — tre driftstilstande med audit-log: **Normal drift**, tidsbegrænset **Pause** (5–1440 min; stopper modellen og frigiver RAM, analysejob udskydes i kø) og tidsbegrænset **Brug lav-memory** (kun vision-modeller under 4 GB, fx `llava-phi3` — fail-closed, falder aldrig tilbage til en stor model). Tilstanden overlever genstart og genoptages automatisk ved udløb.
  - *Modeller og inferens* — installerede modeller, valg af aktiv model, gem runtime.
  - *Promptversioner* — versionerede prompts med allow-listede variabler; gem kladde pr. formål.
  - *AI Ops vurdering* / *SAST review-signaler* — anbefalinger fra AI-driftanalysen.
  - *Model-opfundne tags* — godkend/afvis/merge tags, dansk oversættelse pr. tag.
  - *Model-nøjagtighed over tid* og *Tag statistik* — grafer og filtrérbar tagliste.
- **Typiske opgaver:** hvis Mac-headenden løber tør for RAM (Google Drive + Qwen kan tage >90 %), sæt *Brug lav-memory* i fx 120 min i stedet for at lade systemet swappe.
- **Fejlfinding:** FAQ'en "Ollama vs Gemini — hvad bruger jeg hvornår?" og "Hvordan opdaterer jeg de selvlærende baselines?".

### Open WebUI (`/openwebui`)

- **Formål:** Integreret AI-assistent (Open WebUI) til natural-language-forespørgsler om systemet.
- **Hvem ser den:** Kun admin (admin-gated route; servicen styres af `headend/openwebui_runtime.py`).
- **Bemærk:** Siden indeholder en eksperimentel sektion ("Peter vil gerne lege med Ollama") — denne del er labs, ikke produktionsfunktion. Open WebUI er en lab-komponent; se DOKUMENTPAKKE-konflikttabellen (status: løst som lab-only med launchd + RBAC).
- **Fejlfinding:** Hvis assistenten ikke svarer, tjek at Open WebUI-agenten kører (launchd) og at Ollama-tilstanden ikke er sat på Pause.

### Compliance (`/compliance`)

Beskrevet i `MENUGUIDE_BRUGER_v1.md` (alle roller kan se den). Admin kan desuden ændre status på GRC-poster og generere rapporter.

---

## Admin-dropdown

### System Admin (`/system-admin`)

- **Formål:** Systemniveau-parametre for edge-flåden og headend.
- **Felter (udvalg, verificeret i koden):**
  - *Relæ/power-cycle:* GPIO-ben for kamera (standard 356) og modem (361), tænd-før (`relay_on_before`, sek), sluk-efter (`relay_off_after`, sek).
  - *Live View:* maks. varighed pr. session (standard 180 s; centralt nødstop kan altid afbryde, jf. politik om maks. 60 min kontinuerlig drift).
  - *Capture:* capture-timeout (60 s), download-timeout (30 s).
  - *Modem-genzindkaldelse:* antal fejl før power-cycle (3), min. interval mellem cycles (600 s), sluk-tid (5 s), recover-tid (15 s).
  - *CMDB-drift-UI* — baseline-drift (pakker/services/konti) pr. enhed; reconciliation køres on-demand via admin-endpoint.
- **Fejlfinding:** Ændringer her distribueres via config-versioningen og træder i kraft ved enhedens næste sync-poll (≤5 min med standardinterval).

### Lokal adgang (`/local-access`)

- **Formål:** Oversigt over **BT PAN TOTP-status for alle kameraer** den indloggede admin har adgang til: hvilket lag i hierarkiet der resolver (global / kunde / site / kamera / ikke-oprettet) og enhedens SID.
- **Vigtigt at vide:** Oversigten viser bevidst **ikke** selve QR-koden eller koden — klik ind på det enkelte kamera for at se dem. Det undgår at duplikere hemmeligheds-visningen til en samlet flade.
- **Typiske opgaver:**
  1. Verificér før site-besøg at alle enheder har et provisioneret secret (og ikke står som "ikke-oprettet").
  2. Spot om mange kameraer arver et globalt fallback-lag — kan være et tegn på manglende per-enhed-provisionering.
- **Relateret:** `SEC-016_Factory_BT_TOTP_Bootstrap_Gap.md`; Kamera-siden nedenfor.

### Brugere (`/users`) — kun super_admin

- **Formål:** Bruger- og rollestyring: opret, rediger, deaktivér; roller og MFA.
- **Roller:** `viewer` < `operator` < `admin` < `super_admin`. MFA er obligatorisk for admin-adgang til følsomme endpoints.
- **Bemærk:** Deaktivering af en anden brugers MFA kræver super_admin + step-up (password/TOTP) og udløser en SIEM-hændelse (`mfa_disabled`) — se R25-lukningen i `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md`.
- **Relateret:** ADMINISTRATORMANUAL §11, §15.

### Nøgler (`/key-management`)

- **Formål:** Credential-livscyklus for API-tokens og nøgler på tværs af CMDB/device/service.
- **Handlinger:**
  - Opret credential: target-ID, label, scopes (kommasepareret), udløb i dage; for Edge SSH **public key only** — headend genererer ikke længere Edge private keys (PR #73, SEC-ZAI-05/15).
  - **Kræv HMAC request-signatur** pr. credential (signature-policy).
  - **Roter** og **Revoker** pr. aktiv credential.
  - Vedligeholdelse: **Migrér legacy-tokens**, **Ryd op i stale credentials** (med og uden bekræftelse — se `STALE_CREDENTIAL_TL-DCA63234D813_RUNBOOK_v1.md` før du rydder rigtige enheder!).
- **Fejlfinding:** En revokeret nøgle slår igennem ved næste kald — ingen caching-grace.

### SSH Tunnels (`/ssh-tunnel`)

- **Formål:** Administrer reverse SSH-tunneler til edge-enheder og åbn **browserterminal**.
- **Terminal-sikkerhed:** Browserterminalen er kun tilgængelig når enhedens SSH host identity er *trusted/verified* — ellers vises "Browserterminal er deaktiveret" med begrundelse. Det er en bevidst fail-closed adfærd, ikke en fejl.
- **Typiske opgaver:** opret tunnel til enhed uden direkte netværksadgang → åbn terminal → kør diagnostik (`systemctl status timelapse-edge`, logs). Begræns sessioner; tunnels er dokumenterede adgangsveje og logges.
- **Relateret:** `Claude_Support_Access_Model_2026-07-06.md`; Edge Runbook §6.

### Opdateringer (`/updates`)

- **Formål:** Hele det governede update-flow: pending updates, artifacts, signerede releases, godkendelse og udrulning til enheder.
- **Sektioner (verificeret):** pending- og historiklisters; *Godkend opdatering #…*-dialog med kommentar og valg af mål-enhed (fx `TL-C87FF9587CA0`); registrering af seneste signerede tag; OS-bundle-håndtering (`TL-OS-YYYYMMDD-...`); change-ticket-binding.
- **Standard-flow (app-opdatering):**
  1. CI bygger fra et signeret tag → artifact katalogiseres.
  2. "Registrer seneste signerede tag" i UI.
  3. Opret/attach change ticket; review SBOM og teststatus.
  4. Godkend for enhed(er) → enheden henter og installerer ved næste sync-poll; post-restart health-gate skal bestå (PR #56), ellers rulles tilbage.
- **Regler:** Edge må **aldrig** bruge direkte apt/internet — OS-opdateringer distribueres kun som Headend-signeret offline bundle. Direkte teknisk approval er til lab/nødbrug; produktion bør gå gennem change ticket (se `Update_Flow_v10.md` §Bruger Manual).
- **Fejlfinding:** Hvis en enhed ikke opdaterer: tjek at den har rapporteret `app_version` via sync-poll, at opdateringen er godkendt for netop den enhed, og at artifact'et indeholder den pågældende kode (jf. NPU-runner-sagen 2026-08-19).
- **Relateret:** `kimi-update-flow-2026-08-15.md` (uafhængig review), `Update_Flow_v10.md`.

### Change tickets (`/change-tickets`)

- **Formål:** Change management: opret ticket fra en update (indtast update-ID), gennemse, godkend eller afvis — alt signeres (`content_sha256` + signatur gensigneres automatisk når SBOM/artifact-felter ændres).
- **Felter:** titel, status, audit-noter (tekstfelt før godkend/afvis), bundet artifact og SBOM-reference.
- **Typiske opgaver:**
  1. Før godkendelse: kontrollér at ticket har bundet SBOM/test-evidens (feltet kan stadig være tomt — der er endnu ingen tvungen politik, se GO_LIVE-tilføjelse 2026-07-05).
  2. Brug audit-noten til at dokumentere *hvorfor* — den indgår i det signede dokument.

### Post-processing (`/post-processing`)

- **Formål:** Efterbehandling af captures: render-jobs, billedpipelines og AI-worker-overvågning.
- **Felter:** billedantal-grænse ("Tom = alle billeder, ingen øvre grænse"), **exposure/WB-ramping-checkbox** (temporal udjævning af eksponering og hvidbalance; default fra; originaler røres aldrig — korrektion sker på job-scopede kopier med fallback ved enhver fejl), *AI-worker — faktisk fremskridt*-panel.
- **Relateret:** `TIMELAPSE_BILLEDKVALITET_OG_VIDEOARKITEKTUR_v1.md`.

### CMDB (`/cmdb`)

- **Formål:** Configuration Management Database: enheder, software-inventory, relationer, konfigurationshistorik og baseline-drift.
- **Sektioner:** enhedsliste med *AI CMDB-analyse*; detaljeside pr. enhed (`/cmdb/:deviceId`) med inventory (pakker, enabled services, lokale konti), drift-mod-baseline (manglende **og** uventede services/konti — begge retninger siden 2026-08-16), SSH-tunnel-genvej og **break-glass-konti** (opret/checkout med auto-rotation).
- **Bemærk (vigtig):** Break-glass-modellen her (password-baseret, Fernet-krypteret) har endnu **ikke** sin edge-side implementeret, og forholder sig til en ældre, aldrig-merget pubkey-model — se `kimi-grc-afventer-2026-08-19.md` punkt 2 før du baserer en nødprocedure på den.
- **Relateret:** `README_CMDB.md`.

### Import (`/import`)

- **Formål:** Importér historiske/eksterne billedarkiver ind som kamera-lokationer.
- **Flow (to trin + jobs):**
  1. *Vælg destination* — kunde → site → navngiv kamera-lokation (fx "Kamera 2 — Historisk").
  2. *Vælg kilde* — upload eller server-sti (fx `/path/to/archive`).
  3. Start job og følg det i joblisten (auto-opdaterer).
- **Bemærk:** Importerede kameraer oprettes som **virtuelle devices** (`TL-IMPORT-*`, status `import`, ingen heartbeat). De må **aldrig** behandles som forældreløse ved oprydning — de er slettet to gange ved en fejl (se `FIND-VIRTUAL-DEVICE-CLEANUP-001/002`).
- **Fejlfinding:** Hvis importerede kameraer ikke kan ses i UI, tjek at `devices`-rækker og `device_assignments` stadig er intakte (se handover 2026-08-16 14:26).

### SIEM (`/siem`)

- **Formål:** Sikkerhedshændelser og audit på tværs af headend, edge og eksterne kilder.
- **Sektioner:**
  - *AI SIEM-analyse* — AI-genereret opsummering med knap til at anvende foreslåede filtre direkte.
  - *Hændelsesoverblik* + *Aktiv risiko* — scorede risici med filtre.
  - *Event-typer*, *Per enhed* — opdelinger.
  - Kildetabs: **Headend**, **Edge journal**, **Syslog**, **GitHub og eksterne kilder**.
  - *Aktiv SIEM-politik* og *Konfiguration*.
  - Klik en hændelse → detaljepanel med kernefelter og handlinger: filtrér videre på device, event-type eller severity med ét klik.
- **Dataflow:** Edge sender SIEM-events som del af den konsoliderede sync-poll (siden 2026-08-19) — ikke som separat POST.
- **Typiske opgaver:** undersøg `mfa_disabled`, `device_token`-afvisninger og auth-fejl; verificér at standard admin-password-advarslen (C-03) ikke fremgår af Headend-loggen.

### Retention (`/retention`)

- **Formål:** GDPR retention-politikker: hvor længe captures og logs gemmes, automatisk sletning og undtagelser.
- **Felter:** politik-oversigt, *Handlinger* pr. politik (aktivér/kør/evaluér), filtre på kamera-ID og device-ID.
- **Relateret:** `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`; BRUGERMANUAL §7.2.

### GDPR Sløring (`/redaction`)

- **Formål:** Review-workflow for automatisk sløring af persondata i billeder (ansigter, nummerplader m.m.).
- **Flow:** vælg billede fra listen → se *Fundet GDPR data* (detektioner) → godkend/afvis sløringsforslag pr. fund → status opdateres.
- **Bemærk:** Sløring er tenant-scoped (lukket GDPR-redaction-isolation-gap, 2026-08-15); du ser kun captures for kunder du har adgang til.
- **Relateret:** `SEC-001_Redaction_API_Missing_Auth.md`, `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`.

### Drift (`/observability`)

- **Formål:** Driftsovervågning: system-health, per-scope-tiles (global/kunde/site/enhed), adgangs-log på billedniveau og log-genveje.
- **Sektioner:**
  - *Logs & hændelser* med genvej til SIEM.
  - Hurtiglinks til relaterede sider.
  - *Adgangs-log:* filtrér på bruger, edge/device og filnavn — viser hvem der har set/downloadet hvilke billeder (G-05).
  - *Notifikationsopsætning*-genvej.
  - Scope-tiles med tidsvindue-vælger (timer) og drill-down til kilden.
- **Typiske opgaver:** "har nogen set dette billede?" → filtrér på filnavn. "Er enheden X ustabil?" → åbn dens tile og se trend over valgt tidsvindue.
- **Relateret:** `Claude_Observability_ITIM_Design_2026-06-29.md`.

---

## Admin-sider uden menupunkt

### Kamera-siden (`/cameras/:deviceId`)

- **Formål:** Alt om ét kamera: identitet, AI-kontekst, drift-analyse, parameter-overrides og lokal adgang (BT PAN TOTP).
- **Sektioner:**
  - *Kamera identitet* — visningsnavn (fx "Kamera 1 — Nordøst") og binding til kunde/site.
  - *AI-kontekst* — to fritekstfelter der styrer AI-analysens dømmekraft: *scenarie-beskrivelse* (hvad kameraet ser, hvad der er normalt) og *kendte forstyrrelser* (fx "nabogrund under byggeri — kran dér er normal").
  - *Drift-analyse* — billeddrift over tid.
  - *Parameter-overrides* pr. sektion — tom = arv fra overliggende lag.
  - *BT PAN TOTP* — QR-kode og **live roterende 6-cifret kode** (opdateres hvert 30. sek., kun mens panelet er åbent). Bruges til lokal tekniker-login på enheden via Bluetooth PAN.
- **Sikkerhed:** QR/kode vises kun her (ikke i oversigter); adgang kræver admin + tenant-scoping.
- **Relateret:** `SEC-016_Factory_BT_TOTP_Bootstrap_Gap.md`.

### Kamera-laboratoriet (`/lab/:deviceId`)

- **Formål:** Kontrolleret test af kameraindstillinger mod enheden i LAB mode (manual fokus, eksponeringsmatrix, live view).
- **Bemærk:** LAB mode er eksplicit og tidsbegrænset; centralt nødstop kan altid afbryde. En enhed der hænger i LAB: se FAQ'en "LAB mode hænger — 'Venter på kamera'".
- **Relateret:** `docs/LAB_MODE_TEST_GUIDE.md`, `Nikon_Z30_LAB_Profil_og_Fokus_2026-06-22.md`.

### Ny kunde (`/customers/new`) — kun super_admin

- **Formål:** Opret kunde med stamdata; herefter sites og kameraer via kundesiden.

---

## Se også

- `MENUGUIDE_BRUGER_v1.md` — bruger-siderne.
- `FAQ_og_fejlsøgning.md` — fejlfinding spørgsmål/svar.
- `ADMINISTRATORMANUAL_v10.md` — CLI-/driftsprocedurer (backup, provisioning, GPG, nginx, DB).
- `Update_Flow_v10.md` — det fulde update-flow med gates.
