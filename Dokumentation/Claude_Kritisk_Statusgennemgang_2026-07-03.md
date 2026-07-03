# TimeLapse Pro — Kritisk statusgennemgang (ny Claude-session)

**Dato:** 2026-07-03
**Forfatter:** Claude (ny session — onboardet via `00_START_HER.md`, `HANDOVER_LOG.md`, `HANDOVER_2026-07-02_Claude_session.md`, `HANDOVER_Claude_Codex_arbejdsdeling.md`)
**Formål:** Frisk, kritisk kig — først dokumentation (alle 17 autoritative v10-dokumenter + levende dokumenter + designnotater), dernæst kildekode med "nye øjne". Ingen kodeændringer i denne omgang. Til fælles gennemgang: Peter, Claude, Codex.
**Metode:** Læsning af hele `Dokumentation/`-korpus + målrettet kodegennemgang af `headend/main.py`, `headend/cmdb.py`, `headend/siem.py`, `headend/itim.py`, `edge/security.py`, `edge/agent.py`, `timelapse-ui/src/api/client.ts`, `timelapse-ui/src/context/AuthContext.tsx`, `.github/workflows/ci.yml`, `headend/requirements.txt`, git-historik og repo-hygiejne. Alle fund nedenfor er verificeret direkte i den aktuelle kode (fil + linjehenvisning), ikke kun i dokumentation.

---

## 1. Overordnet vurdering

Dokumentationskorpus er usædvanligt modent og selvkritisk — I har allerede en fælles risikovurdering, go-live-checkliste, kravregister og et system-health-register, og I fanger selv mange af jeres egne problemer (SFTP-hærdning, HMAC, path-traversal-forsvar på billed-endpoints, Ed25519 edge-signering med korrekte fil-rettigheder og timing-safe sammenligning). Det er ikke normalt at se et projekt på denne skala dokumentere sine egne huller så ærligt. Det skal sige noget: I gør allerede det rigtige på processen.

Men ved at gå direkte i koden med et frisk blik fandt jeg **flere reelle, konkrete huller, som ikke er fanget af den eksisterende dokumentation** — herunder ét jeg vurderer kritisk (uautentificeret adgang til jeres SIEM/threat-data) og ét systemisk (MFA-politikken håndhæves kun i én af tre parallelle RBAC-implementeringer). Begge modsiger direkte "✅ Løst"-status i `RISK_ASSESSMENT_v10.md` (R02) og `GO_LIVE_CHECKLIST_v10.md` (C-04, C-07). Det er ikke kritik af arbejdet i sig selv — det er præcis den slags, der er svær at fange uden at læse hver linje, og som retfærdiggør en frisk gennemgang.

Konklusion i én sætning: **LAB-status er retfærdig, men "MFA/RBAC er løst"-vurderingen i de autoritative dokumenter er for optimistisk, og der er nu et konkret, uautentificeret informationslæk, som bør lukkes før noget som helst internet-eksponering — uanset portmigrering.**

---

## 2. Kritiske fund (P0 — bør lukkes uanset LAB/prod)

### 2.1 `/api/siem/*` har ingen autentificering overhovedet

**Fil:** `headend/siem.py` (router monteret i `headend/main.py:10007` som `app.include_router(siem_router, prefix="/api/siem")`, uden `dependencies=[...]`).

`GET /api/siem/events`, `GET /api/siem/summary` og `GET /api/siem/threats` (linje 499, 524, 576) har **kun** `db: Session = Depends(get_db)` — ingen `Depends(get_current_user)`, ingen rolletjek. Alle tre kan kaldes helt uden login og returnerer sikkerhedshændelser, source-IP'er på mislykkede login/SSH-forsøg, brute-force-kandidater og kritiske hændelser pr. device.

`POST /api/siem/events/{device_id}` (linje 445) — hvor node-agenter poster events — har kun en rate-limiter (`_check_api_rate_limit`), ingen HMAC/token-verifikation af hvem der poster. Det betyder at hvem som helst kan indsprøjte fabrikerede security events for et vilkårligt `device_id` (log-forurening, falske kritiske alarmer, eller camouflage af et rigtigt angreb i støj).

**Hvorfor det er alvorligt lige nu:** nginx lytter stadig på public `*:80`/`*:443` (bekræftet live af Codex 2026-07-02). Det betyder dette ikke er et teoretisk lab-fund — hvis porten er nået udefra i dag, er jeres SIEM-data det også. Det modsiger direkte SEC-004 ("RBAC med 4 roller ✅ Implementeret") og C-04 ("RBAC aktivt på alle `/api/admin/*` endpoints ✅") — bemærk at `/api/siem/*` slet ikke er under `/api/admin/*`, så det er formentlig faldet uden for scope for de tidligere reviews, som fokuserede på `/api/admin/*` og `/api/cmdb/*`.

**Anbefaling:** tilføj `dependencies=[Depends(require_role("viewer"))]` på router-niveau for GET-endpoints, og krav om gyldig device-HMAC (samme mønster som `/api/heartbeat`) på `POST /events/{device_id}`. Lille, isoleret rettelse — bør kunne lukkes samme dag den godkendes.

### 2.2 MFA-politikken håndhæves kun i én af tre parallelle RBAC-implementeringer

I har (mindst) tre uafhængige "kræv rolle"-funktioner i kodebasen:

- `headend/main.py:751` `require_role()` — tjekker rolle **og** kalder `_mfa_required_for_user()` + `_session_is_mfa_verified()` (linje 761).
- `headend/cmdb.py:104` `_require_cmdb_role()` — tjekker kun rolle. Ingen MFA-kald nogen steder i filen.
- `headend/itim.py:776` `_require_role()` — samme mønster, kun rolle, ingen MFA-kald.

Det betyder at **hele CMDB-routeren** (inventory, SBOM, update-pipeline, og især `checkout_break_glass` i `headend/cmdb.py:795`, som udleverer et dekrypteret admin-password) og **hele ITIM-routeren** kan tilgås af en super_admin/admin-session, der aldrig har gennemført MFA — stik imod politikken I netop har rullet ud og dokumenteret som "✅ Løst 2026-07-02" i `RISK_ASSESSMENT_v10.md` R02 og `GO_LIVE_CHECKLIST_v10.md` C-07.

Dette er et klassisk "policy enforcement point"-problem: MFA-tjekket er kodet ét sted (rigtigt) i stedet for i en delt, genbrugt afhængighed alle routere trækker på — og de to andre routere er kommet til uden at arve kontrollen. Sandsynligheden for at det sker igen i næste router (I har allerede mønsteret 3 gange) er høj, medmindre det centraliseres.

**Anbefaling:** træk `require_role`+MFA-logikken ud i ét delt modul (fx `headend/authdeps.py`) som `cmdb.py`, `siem.py`, `itim.py` og fremtidige routere importerer — i stedet for at hver fil definerer sin egen "lokale bro" til `main._ROLE_HIERARCHY`. Det er også den rigtige lejlighed til at rette 2.1 samtidig.

### 2.3 Break-glass password-checkout mangler sin egen dokumenterede sikring

`headend/cmdb.py:795` `checkout_break_glass()` har selv en kommentar i koden: *"SIKKERHED: Denne endpoint skal i produktion kræve: 1. Stærk MFA … 2. IP-whitelisting 3. Rate limiting"*. Alle tre er implementeret som **opt-in via miljøvariabler** (`TIMELAPSE_BREAKGLASS_IP_ALLOWLIST`, `TIMELAPSE_BREAKGLASS_CHECKOUT_MAX_PER_HOUR`) og er **fra af som default** — kombineret med 2.2 (ingen MFA-tjek i `cmdb.py` overhovedet) betyder det, at endpointet i dag reelt kun er beskyttet af `role=admin` + en almindelig session-cookie. Dette er samme punkt, som jeres eget observability-designnotat (`Claude_Observability_ITIM_Design_2026-06-29.md` §11) allerede har flagget som et "reelt SABSA-/compliance-hul" — bekræftet her direkte i koden.

**Anbefaling:** gør MFA-krav, rate-limit og (hvis muligt) IP-scope til hård default for break-glass, ikke opt-in.

### 2.4 Tenant-isolation for billeddata er 100% applikationsdisciplin, ikke en databasegaranti

`Capture`-modellen (`headend/database.py:112`) har **ikke** en `customer_id`-kolonne — kun `device_id`. Kunde-isolation for jeres mest følsomme datatype (byggepladsbilleder, potentielt med personer) sker udelukkende via manuelle joins/hjælpefunktioner (`_ensure_capture_device_access`, 30 kaldesteder; `_ensure_capture_file_access`, 6 kaldesteder) i `main.py`, som Codex også selv bemærkede i valideringsnotatet 2026-07-02 ("RBAC skal beskrives som API-/join-baseret tenant scoping, ikke som en fysisk sikkerhedsgaranti"). Der er 14 steder i `main.py` der querier `Capture` direkte — jeg har ikke verificeret hver enkelt linje for korrekt scoping (det kræver en systematisk gennemgang), men arkitekturen betyder, at **én glemt kontrol i ét nyt eller ændret endpoint er et cross-tenant datalæk**, uden at nogen database-constraint fanger det.

Givet at Confidentiality er en KRITISK SABSA-attribut i jeres eget dokument, og at dette er GDPR Art. 32-relevant kundedata, vurderer jeg dette som et arkitektonisk P0/P1-emne, ikke kun et kodefund.

**Anbefaling:** (a) en engangs, systematisk audit af alle 14 `db.query(Capture)`-steder mod tenant-scoping, (b) en automatiseret "kunde A kan ikke se kunde B's billeder"-kontrakttest i CI (Codex har allerede foreslået præcis dette punkt 8 i sin v11-valideringsliste — jeg er enig), (c) på sigt: denormaliseret `customer_id` direkte på `captures` som et andet uafhængigt håndtag, ikke kun via `device_id`-join.

---

### 2.5 Kamera-lokation ↔ Edge-binding: datamodellen er der, men billeder/galleri er aldrig koblet på (bekræfter Peters mistanke)

Peter spurgte specifikt ind til dette, og mistanken er bekræftet i kode. Den ønskede adskillelse — en logisk **kamera-lokation** (hvor billeder hører hjemme, med sin egen konfiguration) som en fysisk **Edge-enhed** kan tilkobles, udskiftes eller genbruges under — er **halvt bygget**:

**Det der virker (bekræftet i kode):**
- `Camera` (`headend/database.py:221`) er en selvstændig logisk entitet med egen `config`, `baseline_description`, GPS/orientering osv. — helt adskilt fra `Device`.
- `DeviceAssignment` (`headend/database.py:266`) er en rigtig historik-tabel: `device_id` + `camera_id` + `assigned_at`/`unassigned_at` (null = aktiv) + `assignment_type`. Det er præcis den model, man skal bruge til "udskift defekt Edge, behold lokation".
- `POST /api/admin/cameras/{camera_id}/assign` (`main.py:4100`) håndterer omtildeling korrekt: lukker eksisterende aktiv assignment for både kamera og device, opretter en ny, og synkroniserer `customer_id`/`site_id`/`camera_name` til den nye device for bagudkompatibilitet. Der findes også `GET /api/admin/cameras/{camera_id}/history` (`main.py:4158`), som viser hele assignment-historikken.
- `GET /api/admin/config-resolution?camera_id=...` bruger `DeviceAssignment` til at slå konfigurationslaget op korrekt — så **konfiguration** følger kamera-lokationen rigtigt, selv efter en Edge-udskiftning.

**Det der IKKE virker — kernen i Peters observation:**
- `Capture` (`headend/database.py:112`) har **kun** `device_id`. Ingen `camera_id`-kolonne. Der findes intet sted i koden, hvor et `db.query(Capture)` joiner via `DeviceAssignment` for at slå kamera-lokationen op (grep efter alle 17 `db.query(Capture)`-steder + alle `DeviceAssignment`-brug bekræfter det — de to mødes aldrig).
- Konsekvens: hvis I udskifter en defekt Edge og omtildeler den til samme kamera-lokation (som backend-flowet ovenfor faktisk understøtter), får det **nye** device et nyt `device_id`, og alle nye billeder gemmes under det nye ID. De **gamle** billeder bliver stående under det gamle `device_id`. Der er ingen forespørgsel, endpoint eller UI-side, der samler dem som "denne kamera-lokations fulde historik".
- Det ses tydeligst i frontend: selve `CameraPage.tsx` (route `/cameras/:deviceId` i `App.tsx:75`) er nøglet på `deviceId`, ikke `cameraId` — selv siden, der administrerer kamera-lokationen, tager udgangspunkt i en device. Der findes ingen `/cameras/:cameraId`-visning, der siger "her er alt, hvad denne lokation nogensinde har set, uanset hvilken fysisk Edge der tog det". Galleri, tag-søgning, timelapse-video-generering og billed-/thumbnail-endpoints filtrerer alle udelukkende på `device_id` (fx `list_captures()` i `main.py:9559`).

**Hvorfor det er vigtigt, som Peter selv siger:** uden dette bliver "udskift en defekt Edge" i praksis en ny lokation i UI'et, ikke en fortsættelse af den gamle — man mister den sammenhængende billedhistorik og skal selv huske at kigge to steder (gammelt + nyt device) for at se hele forløbet på den fysiske lokation. Det underminerer noget af pointen med at have en logisk kamera-lokation i første omgang.

**Anbefalet rettelse (arkitekturvalg til fælles beslutning, ikke kun kode):**
1. Tilføj `camera_id` (nullable, backfillet) direkte på `Capture` — sæt den ved upload/import ud fra den på det tidspunkt aktive `DeviceAssignment` for den uploadende `device_id`. Det gør fremtidige galleri-/søge-/tenant-forespørgsler enkle og hurtige (samme retning som §2.4's forslag om `customer_id` på `Capture` — de bør løses sammen, evt. i samme migration, da begge handler om at give `Capture` sine egne, stabile fremmednøgler i stedet for kun at gå via `device_id`).
2. Backfill historiske rækker via et engangsscript, der slår `captured_at` op mod `DeviceAssignment.assigned_at`/`unassigned_at`-vinduer pr. `device_id`.
3. Lav en kamera-lokations-centreret visning (`/cameras/:cameraId` eller udvid eksisterende side) der viser fuld billedhistorik + assignment-historik ét sted, og gør `/api/admin/captures` samt tag-søgning i stand til at filtrere på `camera_id` ud over `device_id`.
4. Overvej om `ai_tag_vocabulary`/baseline-læring (`camera_profile.py`) allerede regner rigtigt i denne sammenhæng, eller om den også kun ser på `device_id` og derfor "glemmer" historik ved en Edge-udskiftning — bør tjekkes i samme ombæring.

---

## 3. Høj prioritet (P1)

### 3.1 `headend/requirements.txt` er helt upinnet — og mangler en modul der faktisk bruges

Alle 14 linjer i `headend/requirements.txt` er uden versionsnummer (`fastapi`, `sqlalchemy`, `bcrypt` osv. — ingen `==x.y.z` noget sted). Det underminerer reproducerbare builds, SBOM (CRA Art. 13) og gør en fremtidig upstream-breaking-release til et produktionsudfald uden varsel.

Værre: `main.py` importerer `slowapi` på modulniveau (linje 36-38) og bruger den til login-rate-limiting — men `slowapi` findes slet ikke i `requirements.txt`. En frisk `pip install -r requirements.txt` i et nyt/gendannet miljø crasher øjeblikkeligt ved opstart. Dette er allerede kendt (`GO_LIVE_CHECKLIST_v10.md` H-03, `ADMINISTRATORMANUAL_v10.md` §19) men jeg vil fremhæve konsekvensen: det er en direkte trussel mod jeres egen disaster-recovery/restore-evne, som i forvejen er en P0-blocker (R09/E-01/E-02). En restore-test, I laver i morgen, vil sandsynligvis fejle på dette alene.

**Anbefaling:** pin alle versioner (`pip freeze` fra det kørende venv er et fint udgangspunkt), tilføj `slowapi`, og gør "frisk venv fra requirements.txt starter headend" til en del af CI eller i det mindste af restore-testen.

### 3.2 CI giver falsk tryghed

`.github/workflows/ci.yml` kører: `py_compile` (kun syntakstjek, ikke logik), to test-filer (i alt 996 linjer tests i hele repoet, og jeres eget `SYSTEM_HEALTH_REGISTER.md` HLTH-014 beskriver dem allerede som primært "findes denne streng i filen"-tests frem for adfærdstests), samt frontend `tsc --noEmit` + `npm run build`. Der er **ingen** lint-gate (219 kendte ESLint-fejl er bevidst holdt uden for CI), **ingen** SAST (Bandit/Semgrep), **ingen** dependency-audit (`pip-audit`/`npm audit`) — selvom alle tre er anbefalet gentagne gange i jeres egne `RISK_ASSESSMENT_v10.md` og `TimeLapse_Security_Compliance_v10.md`. "CI er grøn" (H-01 ✅) er derfor et markant svagere signal, end det ser ud til for en læser, der ikke kender detaljerne.

**Anbefaling:** ikke nødvendigvis at gøre lint/SAST blokerende med det samme (219 fejl er meget), men tilføj dem som non-blocking CI-steps, der rapporterer, så trenden er synlig — og planlæg en triage-sprint (allerede i jeres backlog som Sprint H/J).

### 3.3 `main.py` er en monolit på 15.687 linjer

Auth, RBAC, CMDB-nær logik, updates, backup, notifikationer, timelapse-rendering og meget mere ligger i én fil. Det er ikke kun stilistisk — det er direkte medvirkende til fundet i §2.2 (tre steder genopfinder samme "kræv rolle"-logik, fordi det er svært at se og genbruge på tværs af en fil af den størrelse). I har allerede påbegyndt den rigtige retning (cmdb.py, siem.py, itim.py, ai/-pakken er udtrukket) — næste skridt er at udtrække auth/RBAC/MFA til sit eget lille modul, som resten importerer, frem for at hver ny router skriver sin egen "lokale bro".

### 3.4 "Secure by default" afhænger af, at en operatør husker en streng

`JWT_SECRET`-fail-fast (main.py:81-90) slår kun til, hvis `TIMELAPSE_ENV` er **præcis** `"prod"` eller `"production"`; default er `"lab"`. Der findes ingen automatiseret kontrol (CI eller startup-preflight) af, hvilken værdi der rent faktisk er sat i en given udrulning. Kombineret med default-super_admin/"changeme"-oprettelsen (`main.py:714`, `_ensure_super_admin`, kun et `log.warning`, ingen tvungen password-reset-lås) betyder det, at "secure by default" i praksis er "secure hvis nogen huskede at sætte en miljøvariabel korrekt". Dette er præcis den type CRA Art. 10(2)-krav ("secure by default"), jeres eget dokument selv sætter 🟢 på — jeg vil nedgradere den vurdering til 🟡, fordi den korrekte tilstand er opnåelig, men ikke garanteret af systemet selv.

**Anbefaling:** gør `TIMELAPSE_ENV` til et eksplicit, positivt valg uden farligt default (kræv at det sættes, fail-fast hvis fraværende, i stedet for at antage "lab"), og tilføj et startup-preflight-tjek der logger tydeligt (og evt. blokerer) hvis en default-credential-bruger stadig eksisterer.

---

## 4. Middel prioritet (P2) og dokumentationsgab

### 4.1 EU AI Act er slet ikke nævnt — i noget dokument

`Timelapse_pro_full_documentation_v10.md` DEL 9 har dedikerede afsnit til SABSA, COBIT 2019, ISO 27001, IEC 62443, NIS2, CRA og GDPR — men AI Act optræder ingen steder i de ~17 autoritative dokumenter, selvom systemet: (a) kører automatiseret billedklassificering af mennesker/køretøjer/hændelser via Gemini og Ollama, (b) lader denne klassificering fodre en alarm-motor der kan markere "uvedkommende" eller "person om natten" som hændelser, og (c) i `autonomous`/`npu_first`-tilstand lader Edge AI justere kameraets eksponering uden menneskelig godkendelse (`Codex_Edge_AI_NPU_Modes_2026-06-28.md`).

Det er ikke sikkert, at TimeLapse Pro rammer et højrisiko-kategori under Annex III — men "byggepladsovervågning der klassificerer personers tilstedeværelse og adfærd som normal/unormal" er tæt nok på arbejdspladsovervågning til, at det bør *screenes* eksplicit, ikke bare antages ude af scope. Anbefaling: en formel AI Act-screening (provider/deployer-rolle, GPAI-eksponering via Gemini, Art. 50-transparenskrav når AI-tags/alarmer vises til kunder, grænsefladen til Art. 5-forbudte praksisser) — føjet til jeres eksisterende DEL 9-struktur som et nyt afsnit 9.8, på linje med de øvrige standarder.

### 4.2 MFA er politik-korrekt, men reelt ikke gennemført endnu på rigtige konti

Codex' live-validering (2026-07-02 22:39) viste: 0 af 5 `super_admin`/`operator`-brugere har TOTP aktiveret. Mekanismen (tvungen enrollment ved næste login uden permanent lockout) er fornuftigt designet, men `RISK_ASSESSMENT_v10.md` sætter R02 til "✅ Løst — Residualrisiko 🟢 4", hvilket læses som en afsluttet kontrol. Efter jeres egen regel ("empiri vinder over mening") bør residualrisikoen forblive 🟡, indtil enrollment er bekræftet gennemført for de reelle admin-konti — ikke kun for politikkens kode.

### 4.3 Repo-hygiejne: gentagelse af et mønster, I allerede er blevet brændt af én gang

`SYSTEM_HEALTH_REGISTER.md` (HLTH-001) beskriver allerede en historisk hændelse, hvor en NotebookLM-eksport med rå secrets lå utracked i repoet. I dag ligger der stadig tre fulde kildekode-dumps (`TimeLapse_SourceCode_Inventory*.md`, ~2,2 MB hver, alle committed i git, aldrig ryddet op — tilføjet i commit `9340aed`) plus flere store, utrackede filer i repo-roden (`dokumentation.tar.gz`, `timelapse-pro-doc.gz`, `timelapse_headend.db`, `.claude_proxy/`, `.base_image_cache/`). Jeg gennemsøgte dumpene for oplagte secret-mønstre (JWT/BREAK_GLASS/private keys/TOTP) og fandt **ingen** faktiske lækkede værdier — kun selve kildekodens variabel-navne (fx `JWT_SECRET = os.getenv(...)`, som er koden, ikke en hemmelighed). Så her er ingen aktiv lækage. Men mønstret — store, ureviderede eksport-/dump-filer der samler sig i repoet — er strukturelt det samme, som gav jer HLTH-001, og bør lukkes med en vane, ikke kun manuel review: `.gitignore`-regel for `*_Inventory*.md`/lignende dumps, og en pre-commit secret-scanner (fx `gitleaks`) i CI, så det ikke afhænger af, at nogen husker at kigge.

### 4.4 Dødt/forvirrende frontend-kode omkring en "hemmelighed"

`timelapse-ui/src/api/client.ts:23` `bootstrapToken()` kaldes ubetinget ved hver appstart (`main.tsx`) og henter hele `/api/admin/settings`-payloaden for at lede efter en nøgle `settings['api_token']`, som ikke ser ud til at blive produceret nogen steder i backend under det navn (de eneste `api_token`-lignende felter er `sms.api_token`, som maskeres til `••••••••` ved output, og `Device.api_token`, som er noget helt andet). Funktionen er i praksis et no-op i dag, men mønstret — "kig efter en unavngiven hemmelighed i et generelt settings-svar, og gem den permanent i `localStorage` uden udløb" — er skrøbeligt: en fremtidig, urelateret ændring af `/api/admin/settings`, der tilføjer et felt der hedder `api_token`, ville blive cachet i klar tekst i browserens `localStorage` uden at nogen bad om det. God nyhed samtidig: den egentlige session (`tl_session`) ligger korrekt som HttpOnly-cookie — det er kun dette ene, tilsyneladende overflødige felt, der er problemet. Anbefaling: fjern `bootstrapToken()`/`timelapse_api_token`, medmindre der er en aktiv brug af den, jeg har overset.

### 4.5 Positiv rettelse til `DOKUMENTPAKKE_OVERSIGT_v10.md`

Jeres egen uoverensstemmelsestabel siger: *"Ældre docs siger ingen localStorage; aktuel UI bruger localStorage"* om auth-tokens. Ved gennemgang af `AuthContext.tsx` er det reelle billede bedre end det: session-cookien (`tl_session`) er HttpOnly og sat af serveren — det er kun en ikke-følsom brugerprofil (`tl_user`, til UI-visning) og UI-indstillinger (tidszone), der ligger i `localStorage`, plus det formentlig døde `timelapse_api_token`-fund i §4.4. Det er værd at opdatere dokumentet med den mere præcise status, så I ikke bruger tid på at "løse" noget, der reelt allerede er løst rigtigt.

---

## 5. Ting der allerede er godt lavet (værd at bevare, ikke kun kritik)

- `edge/security.py`: HMAC-request-signering, Ed25519 edge-attestering, artifact-tillidstjek med `hmac.compare_digest` (timing-safe), private nøgler skrevet med `O_EXCL`+`0o600`. Solidt håndværk.
- Billed-/thumbnail-endpoints (`main.py:10328` ff.) bruger `path.resolve().relative_to(root.resolve())` som path-traversal-forsvar, kombineret med eksplicit tenant-adgangstjek (`_ensure_capture_file_access`) — rigtigt mønster.
- CORS er sat til én eksplicit origin med `allow_credentials=True` (ikke `*`) — rigtigt.
- SQL i `main.py`/`siem.py` bruger konsekvent parametriserede `text(...)`-forespørgsler; jeg fandt ingen f-string/string-interpolerede SQL-injektionsmønstre i de filer, jeg gennemgik.
- Update-pull-arkitekturen (Edge henter, verificerer, tager backup før install, rapporterer per-target) er et modent, gennemtænkt design, og E2E-testen fra `Update_Flow_v10.md` er reel evidens, ikke kun påstand.

---

## 6. Prioriteret liste til fælles gennemgang

| # | Fund | Prioritet | Status | Ejer (forslag) |
|---|---|---|---|---|
| 1 | `/api/siem/*` uden auth (§2.1) | 🔴 P0 | ✅ Rettet i kode 2026-07-03, branch `claude/security-hardening-2026-07-03` — afventer commit (git-lock, se HANDOVER_LOG) + genstart + live-verifikation | Claude (kode gjort), Codex/Peter (commit + verificér live) |
| 2 | MFA ikke håndhævet i cmdb.py/itim.py (§2.2) | 🔴 P0 | ✅ Rettet i kode 2026-07-03, samme branch — verificeret lokalt (viewer 200, admin-uden-MFA 403, admin-med-MFA 200) | Claude (kode gjort), Codex/Peter (commit + verificér live) |
| 3 | Break-glass mangler hård MFA/rate-limit default (§2.3) | 🔴 P0 | ✅ MFA-delen lukket via fund #2 (samme `_require_cmdb_role`). Rate-limit/IP-allowlist forbliver bevidst opt-in (env-var) | Claude (kode gjort) |
| 4 | Tenant-isolation kun applikationsdisciplin på captures (§2.4) | 🔴 P0/P1 | Åben — se §2.5/fase 2-plan | Claude (audit + test), Peter (beslutning om skemaændring) |
| 5 | requirements.txt upinnet + mangler slowapi (§3.1) | 🟠 P1 | ✅ Rettet i kode 2026-07-03 — pinnet mod en lokal, kørende venv; **skal krydstjekkes mod prod-venv** (`~/.venvs/timelapse-headend`) | Claude (kode gjort), Codex/Peter (krydstjek + commit) |
| 6 | CI uden lint/SAST/dependency-audit (§3.2) | 🟠 P1 | Claude + Codex |
| 7 | main.py monolit — udtræk auth/RBAC/MFA-modul (§3.3) | 🟠 P1 | Claude |
| 8 | Secure-by-default afhænger af TIMELAPSE_ENV-streng (§3.4) | 🟠 P1 | Claude |
| 9 | AI Act-screening mangler (§4.1) | 🟡 P2 | Claude (udkast), Peter (beslutning) |
| 10 | MFA-enrollment ikke reelt gennemført endnu (§4.2) | 🟡 P2 | Peter/Codex (drift) |
| 11 | Repo-hygiejne / dump-filer (§4.3) | 🟡 P2 | Claude (.gitignore + gitleaks-forslag) |
| 12 | Dødt `bootstrapToken()`-kode (§4.4) | 🟢 P3 | Claude |
| 13 | Opdatér `DOKUMENTPAKKE_OVERSIGT_v10.md` localStorage-status (§4.5) | 🟢 P3 | Claude |
| 14 | `Capture` mangler `camera_id` — billedhistorik følger ikke kamera-lokation ved Edge-udskiftning (§2.5) | 🟠 P1 | Claude (skema+backfill), Peter (beslutning) |
| 15 | Tv-overvågningsloven/Databeskyttelsesloven/Arbejdsmiljøloven/RED/CER mangler i DEL 9 (§7) | 🟡 P2 | Claude (udkast), Peter (beslutning) |

Ingen af disse er rettet endnu — dette er bevidst kun observation og rapportering, som aftalt. Jeg foreslår vi tager punkt 1-4 først, da de er små, isolerede rettelser med stor effekt, og fordi 1 og 3 er reelt eksponerede lige nu givet at nginx stadig er public.

---

## 7. Yderligere lovgivning at have på radaren (ud over AI Act)

Peter bad om et tjek for anden relevant lovgivning ud over SABSA/COBIT/ISO 27001/IEC 62443/CRA/NIS2/GDPR/AI Act. Her er dem, jeg vurderer reelt relevante — ingen af dem er nævnt i de 17 autoritative dokumenter i dag, bortset fra CER, som kun nævnes én gang i forbifarten uden eget afsnit (samme mønster som AI Act-manglen i §4.1).

- **Tv-overvågningsloven (lov om tv-overvågning, DK):** den mest konkrete og oversete. Adskilt fra GDPR — regulerer selve det at opsætte kameraovervågning: skiltningspligt hvor der overvåges, hvem der må overvåge hvad (fx offentligt tilgængelige arealer, indgange, vej/sti forbi byggepladsen), og særlige regler for optagelser der viser personer. Byggepladser grænser ofte op til offentlig vej/sti, så dette bør screenes pr. site, ikke kun GDPR-vurderes. Naturligt at lægge ind i samme DPIA-skabelon som §G/9.7 allerede planlægger.
- **Databeskyttelsesloven (DK):** den danske suppleringslov til GDPR — bl.a. regler om behandling af CPR-numre (næppe relevant her) og videre nationale præciseringer. Bør nævnes eksplicit ved siden af GDPR, ikke kun underforstået.
- **Arbejdsmiljøloven + Arbejdstilsynets vejledning om kameraovervågning af medarbejdere:** hvis kameraerne fanger egne eller kundens ansatte (ikke kun "byggepladsen"), er der et selvstændigt spor ud over GDPR: legitimt formål, information til de ansatte, og typisk pligt til at inddrage evt. samarbejdsudvalg/tillidsrepræsentant før overvågning af medarbejderes arbejdsindsats sættes op. Det er kundens (den dataansvarliges) pligt over for egne ansatte, men TimeLapse Pro bør have det med i kundevendt vejledning/DPIA-skabelon, så kunderne rent faktisk bliver gjort opmærksomme på det.
- **Radioudstyrsdirektivet (RED, 2014/53/EU) + cybersikkerheds-delegeretakt 2022/30/EU:** Edge-hardwaren har WiFi, Bluetooth (BT PAN/TOTP) og 4G-modem — det gør den til radioudstyr under RED, med egen CE-mærkningspligt *uafhængigt af CRA*. Delegeretakten om cybersikkerhed (netværksbeskyttelse, privacy/persondatabeskyttelse, svindelbeskyttelse for radioudstyr) er allerede trådt i kraft og har til dels overlappende, men ikke identiske krav med CRA. Bør tilføjes som eget punkt ved siden af CRA-afsnittet (9.6), da det er let at overse, når man kun tænker "software-CRA".
- **CER-direktivet (Critical Entities Resilience):** nævnes i dag kun i forbifarten i `TimeLapse_Security_Compliance_v10.md`'s executive summary, uden eget afsnit — samme gab-mønster som AI Act. Relevans er formentlig lav (I er leverandør, ikke selv en kritisk enhed), men bør have samme korte, eksplicitte vurdering som NIS2 har, i stedet for at stå som et løst navn.
- **GDPR Art. 22 (automatiserede afgørelser/profilering)** — nævnes ikke eksplicit i jeres GDPR-afsnit (9.7). Alarm-motoren, der klassificerer "uvedkommende"/hændelser ud fra AI-tags, ligger tæt på automatiseret beslutningstagning, der kan påvirke personer (fx en sikkerhedsreaktion udløst af en algoritmes vurdering). Bør vurderes sammen med AI Act-punktet i §4.1, ikke som en separat proces.
- **ePrivacy/cookie-bekendtgørelsen** for `www.timelapse-pro.dk`, hvis marketingsitet bruger cookies/analytics — let at overse, fordi det ikke er "produktet", men stadig et lovkrav for jeres egen hjemmeside.
- **Produktansvarsloven:** hvis systemet fejler og det får konsekvenser (fx manglende dokumentation i en byggetvist), er der et almindeligt produktansvarsspor ved siden af CRA's sikkerhedskrav — værd at have i baghovedet, lavere prioritet.
- **Bogføringsloven (digitalt bogføringssystem-krav):** ikke et produkt-/databeskyttelsesspørgsmål, men en generel virksomhedspligt for TimeLapse Pro som selskab — nævnes kun for fuldstændighedens skyld, ikke teknisk relevant for platformen.

Anbefaling: tilføj tv-overvågningsloven, databeskyttelsesloven, arbejdsmiljøloven og RED som nye, korte afsnit i `Timelapse_pro_full_documentation_v10.md` DEL 9 (samme skabelon som de øvrige — introduktion, kontrol-mapping, gaps, leverandør-/kundedokumenter), og giv CER samme behandling som NIS2 i stedet for kun ét nævn. Det er dokumentationsarbejde, ikke kode — kan gøres uafhængigt af punkterne i §2-§4.

---

*Se også: `RISK_ASSESSMENT_v10.md`, `GO_LIVE_CHECKLIST_v10.md`, `KRAVREGISTER_og_STATUS_v10.md`, `SYSTEM_HEALTH_REGISTER.md`, `HANDOVER_Claude_Codex_arbejdsdeling.md`.*
