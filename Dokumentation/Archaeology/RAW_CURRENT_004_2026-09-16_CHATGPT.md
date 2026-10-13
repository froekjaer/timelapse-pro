# Raw archaeology extract — current 004

## Dokumentation/Claude_Kritisk_Statusgennemgang_2026-07-03.md

1: # TimeLapse Pro — Kritisk statusgennemgang (ny Claude-session)
6: **Metode:** Læsning af hele `Dokumentation/`-korpus + målrettet kodegennemgang af `headend/main.py`, `headend/cmdb.py`, `headend/siem.py`, `headend/itim.py`, `edge/security.py`, `edge/agent.py`, `timelapse-ui/src/api/client.ts`, `timelapse-ui/src/context/AuthContext.tsx`, `.github/workflows/ci.yml`, `headend/requirements.txt`, git-historik og repo-hygiejne. Alle fund nedenfor er verificeret direkte i den aktuelle kode (fil + linjehenvisning), ikke kun i dokumentation.
10: ## 1. Overordnet vurdering
12: Dokumentationskorpus er usædvanligt modent og selvkritisk — I har allerede en fælles risikovurdering, go-live-checkliste, kravregister og et system-health-register, og I fanger selv mange af jeres egne problemer (SFTP-hærdning, HMAC, path-traversal-forsvar på billed-endpoints, Ed25519 edge-signering med korrekte fil-rettigheder og timing-safe sammenligning). Det er ikke normalt at se et projekt på denne skala dokumentere sine egne huller så ærligt. Det skal sige noget: I gør allerede det rigtige på processen.
16: Konklusion i én sætning: **LAB-status er retfærdig, men "MFA/RBAC er løst"-vurderingen i de autoritative dokumenter er for optimistisk, og der er nu et konkret, uautentificeret informationslæk, som bør lukkes før noget som helst internet-eksponering — uanset portmigrering.**
20: ## 2. Kritiske fund (P0 — bør lukkes uanset LAB/prod)
22: ### 2.1 `/api/siem/*` har ingen autentificering overhovedet
32: **Anbefaling:** tilføj `dependencies=[Depends(require_role("viewer"))]` på router-niveau for GET-endpoints, og krav om gyldig device-HMAC (samme mønster som `/api/heartbeat`) på `POST /events/{device_id}`. Lille, isoleret rettelse — bør kunne lukkes samme dag den godkendes.
34: ### 2.2 MFA-politikken håndhæves kun i én af tre parallelle RBAC-implementeringer
48: ### 2.3 Break-glass password-checkout mangler sin egen dokumenterede sikring
50: `headend/cmdb.py:795` `checkout_break_glass()` har selv en kommentar i koden: *"SIKKERHED: Denne endpoint skal i produktion kræve: 1. Stærk MFA … 2. IP-whitelisting 3. Rate limiting"*. Alle tre er implementeret som **opt-in via miljøvariabler** (`TIMELAPSE_BREAKGLASS_IP_ALLOWLIST`, `TIMELAPSE_BREAKGLASS_CHECKOUT_MAX_PER_HOUR`) og er **fra af som default** — kombineret med 2.2 (ingen MFA-tjek i `cmdb.py` overhovedet) betyder det, at endpointet i dag reelt kun er beskyttet af `role=admin` + en almindelig session-cookie. Dette er samme punkt, som jeres eget observability-designnotat (`Claude_Observability_ITIM_Design_2026-06-29.md` §11) allerede har flagget som et "reelt SABSA-/compliance-hul" — bekræftet her direkte i koden.
52: **Anbefaling:** gør MFA-krav, rate-limit og (hvis muligt) IP-scope til hård default for break-glass, ikke opt-in.
54: ### 2.4 Tenant-isolation for billeddata er 100% applikationsdisciplin, ikke en databasegaranti
56: `Capture`-modellen (`headend/database.py:112`) har **ikke** en `customer_id`-kolonne — kun `device_id`. Kunde-isolation for jeres mest følsomme datatype (byggepladsbilleder, potentielt med personer) sker udelukkende via manuelle joins/hjælpefunktioner (`_ensure_capture_device_access`, 30 kaldesteder; `_ensure_capture_file_access`, 6 kaldesteder) i `main.py`, som Codex også selv bemærkede i valideringsnotatet 2026-07-02 ("RBAC skal beskrives som API-/join-baseret tenant scoping, ikke som en fysisk sikkerhedsgaranti"). Der er 14 steder i `main.py` der querier `Capture` direkte — jeg har ikke verificeret hver enkelt linje for korrekt scoping (det kræver en systematisk gennemgang), men arkitekturen betyder, at **én glemt kontrol i ét nyt eller ændret endpoint er et cross-tenant datalæk**, uden at nogen database-constraint fanger det.
60: **Anbefaling:** (a) en engangs, systematisk audit af alle 14 `db.query(Capture)`-steder mod tenant-scoping, (b) en automatiseret "kunde A kan ikke se kunde B's billeder"-kontrakttest i CI (Codex har allerede foreslået præcis dette punkt 8 i sin v11-valideringsliste — jeg er enig), (c) på sigt: denormaliseret `customer_id` direkte på `captures` som et andet uafhængigt håndtag, ikke kun via `device_id`-join.
64: ### 2.5 Kamera-lokation ↔ Edge-binding: datamodellen er der, men billeder/galleri er aldrig koblet på (bekræfter Peters mistanke)
70: - `DeviceAssignment` (`headend/database.py:266`) er en rigtig historik-tabel: `device_id` + `camera_id` + `assigned_at`/`unassigned_at` (null = aktiv) + `assignment_type`. Det er præcis den model, man skal bruge til "udskift defekt Edge, behold lokation".
79: **Hvorfor det er vigtigt, som Peter selv siger:** uden dette bliver "udskift en defekt Edge" i praksis en ny lokation i UI'et, ikke en fortsættelse af den gamle — man mister den sammenhængende billedhistorik og skal selv huske at kigge to steder (gammelt + nyt device) for at se hele forløbet på den fysiske lokation. Det underminerer noget af pointen med at have en logisk kamera-lokation i første omgang.
82: 1. Tilføj `camera_id` (nullable, backfillet) direkte på `Capture` — sæt den ved upload/import ud fra den på det tidspunkt aktive `DeviceAssignment` for den uploadende `device_id`. Det gør fremtidige galleri-/søge-/tenant-forespørgsler enkle og hurtige (samme retning som §2.4's forslag om `customer_id` på `Capture` — de bør løses sammen, evt. i samme migration, da begge handler om at give `Capture` sine egne, stabile fremmednøgler i stedet for kun at gå via `device_id`).
85: 4. Overvej om `ai_tag_vocabulary`/baseline-læring (`camera_profile.py`) allerede regner rigtigt i denne sammenhæng, eller om den også kun ser på `device_id` og derfor "glemmer" historik ved en Edge-udskiftning — bør tjekkes i samme ombæring.
89: ## 3. Høj prioritet (P1)
91: ### 3.1 `headend/requirements.txt` er helt upinnet — og mangler en modul der faktisk bruges
95: Værre: `main.py` importerer `slowapi` på modulniveau (linje 36-38) og bruger den til login-rate-limiting — men `slowapi` findes slet ikke i `requirements.txt`. En frisk `pip install -r requirements.txt` i et nyt/gendannet miljø crasher øjeblikkeligt ved opstart. Dette er allerede kendt (`GO_LIVE_CHECKLIST_v10.md` H-03, `ADMINISTRATORMANUAL_v10.md` §19) men jeg vil fremhæve konsekvensen: det er en direkte trussel mod jeres egen disaster-recovery/restore-evne, som i forvejen er en P0-blocker (R09/E-01/E-02). En restore-test, I laver i morgen, vil sandsynligvis fejle på dette alene.
99: ### 3.2 CI giver falsk tryghed
103: **Anbefaling:** ikke nødvendigvis at gøre lint/SAST blokerende med det samme (219 fejl er meget), men tilføj dem som non-blocking CI-steps, der rapporterer, så trenden er synlig — og planlæg en triage-sprint (allerede i jeres backlog som Sprint H/J).
105: ### 3.3 `main.py` er en monolit på 15.687 linjer
109: ### 3.4 "Secure by default" afhænger af, at en operatør husker en streng
111: `JWT_SECRET`-fail-fast (main.py:81-90) slår kun til, hvis `TIMELAPSE_ENV` er **præcis** `"prod"` eller `"production"`; default er `"lab"`. Der findes ingen automatiseret kontrol (CI eller startup-preflight) af, hvilken værdi der rent faktisk er sat i en given udrulning. Kombineret med default-super_admin/"changeme"-oprettelsen (`main.py:714`, `_ensure_super_admin`, kun et `log.warning`, ingen tvungen password-reset-lås) betyder det, at "secure by default" i praksis er "secure hvis nogen huskede at sætte en miljøvariabel korrekt". Dette er præcis den type CRA Art. 10(2)-krav ("secure by default"), jeres eget dokument selv sætter 🟢 på — jeg vil nedgradere den vurdering til 🟡, fordi den korrekte tilstand er opnåelig, men ikke garanteret af systemet selv.
117: ## 4. Middel prioritet (P2) og dokumentationsgab
119: ### 4.1 EU AI Act er slet ikke nævnt — i noget dokument
123: Det er ikke sikkert, at TimeLapse Pro rammer et højrisiko-kategori under Annex III — men "byggepladsovervågning der klassificerer personers tilstedeværelse og adfærd som normal/unormal" er tæt nok på arbejdspladsovervågning til, at det bør *screenes* eksplicit, ikke bare antages ude af scope. Anbefaling: en formel AI Act-screening (provider/deployer-rolle, GPAI-eksponering via Gemini, Art. 50-transparenskrav når AI-tags/alarmer vises til kunder, grænsefladen til Art. 5-forbudte praksisser) — føjet til jeres eksisterende DEL 9-struktur som et nyt afsnit 9.8, på linje med de øvrige standarder.
125: ### 4.2 MFA er politik-korrekt, men reelt ikke gennemført endnu på rigtige konti
127: Codex' live-validering (2026-07-02 22:39) viste: 0 af 5 `super_admin`/`operator`-brugere har TOTP aktiveret. Mekanismen (tvungen enrollment ved næste login uden permanent lockout) er fornuftigt designet, men `RISK_ASSESSMENT_v10.md` sætter R02 til "✅ Løst — Residualrisiko 🟢 4", hvilket læses som en afsluttet kontrol. Efter jeres egen regel ("empiri vinder over mening") bør residualrisikoen forblive 🟡, indtil enrollment er bekræftet gennemført for de reelle admin-konti — ikke kun for politikkens kode.
129: ### 4.3 Repo-hygiejne: gentagelse af et mønster, I allerede er blevet brændt af én gang
131: `SYSTEM_HEALTH_REGISTER.md` (HLTH-001) beskriver allerede en historisk hændelse, hvor en NotebookLM-eksport med rå secrets lå utracked i repoet. I dag ligger der stadig tre fulde kildekode-dumps (`TimeLapse_SourceCode_Inventory*.md`, ~2,2 MB hver, alle committed i git, aldrig ryddet op — tilføjet i commit `9340aed`) plus flere store, utrackede filer i repo-roden (`dokumentation.tar.gz`, `timelapse-pro-doc.gz`, `timelapse_headend.db`, `.claude_proxy/`, `.base_image_cache/`). Jeg gennemsøgte dumpene for oplagte secret-mønstre (JWT/BREAK_GLASS/private keys/TOTP) og fandt **ingen** faktiske lækkede værdier — kun selve kildekodens variabel-navne (fx `JWT_SECRET = os.getenv(...)`, som er koden, ikke en hemmelighed). Så her er ingen aktiv lækage. Men mønstret — store, ureviderede eksport-/dump-filer der samler sig i repoet — er strukturelt det samme, som gav jer HLTH-001, og bør lukkes med en vane, ikke kun manuel review: `.gitignore`-regel for `*_Inventory*.md`/lignende dumps, og en pre-commit secret-scanner (fx `gitleaks`) i CI, så det ikke afhænger af, at nogen husker at kigge.
133: ### 4.4 Dødt/forvirrende frontend-kode omkring en "hemmelighed"
137: ### 4.5 Positiv rettelse til `DOKUMENTPAKKE_OVERSIGT_v10.md`
143: ## 5. Ting der allerede er godt lavet (værd at bevare, ikke kun kritik)
153: ## 6. Prioriteret liste til fælles gennemgang
157: | 1 | `/api/siem/*` uden auth (§2.1) | 🔴 P0 | ✅ Rettet, committet (`b0e224c`) og **live-verificeret** 2026-07-03 (Peter): health `200`, `GET /api/siem/events` uden auth → `401` | Claude (kode), Peter (deploy + verifikation) |
158: | 2 | MFA ikke håndhævet i cmdb.py/itim.py (§2.2) | 🔴 P0 | ✅ Rettet, committet (`b0e224c`) og **live-verificeret** 2026-07-03 (Peter) — forinden lokalt bekræftet: viewer 200, admin-uden-MFA 403, admin-med-MFA 200 | Claude (kode), Peter (deploy + verifikation) |
159: | 3 | Break-glass mangler hård MFA/rate-limit default (§2.3) | 🔴 P0 | ✅ MFA-delen lukket via fund #2 (samme `_require_cmdb_role`), live med samme commit. Rate-limit/IP-allowlist forbliver bevidst opt-in (env-var) | Claude (kode gjort) |
160: | 4 | Tenant-isolation kun applikationsdisciplin på captures (§2.4) | 🔴 P0/P1 | ✅ **Fuldt lukket 2026-07-03 (fase 3), godkendt af Peter.** `camera_id`/`customer_id` tilføjet til `Capture` (v12, fase 2), og adgangskontrol (`_capture_is_allowed`/`_capture_tenant_clause`) bruger nu `customer_id` (frosset ved optagelsestidspunkt) som primær kilde i stedet for et live device-opslag — se R16 i `RISK_ASSESSMENT_v10.md` for det konkrete lækage-scenarie dette lukker (Edge-enhed gentildelt til ny kunde). Verificeret med TestClient (7 tests + 1 kant-tilfælde). **Åbent:** post-processing/AI-batch-jobbets device-filter er bevidst ikke opdateret (lav konfidentialitetsrisiko, se §6 nedenfor) | Claude (kode+test gjort), Peter (deploy + live-verifikation) |
161: | 5 | requirements.txt upinnet + mangler slowapi (§3.1) | 🟠 P1 | ✅ Rettet, committet (`b0e224c`) og **installeret i prod-venv** af Peter | Claude (kode), Peter (deploy) |
162: | 6 | CI uden lint/SAST/dependency-audit (§3.2) | 🟠 P1 | Claude + Codex |
163: | 7 | main.py monolit — udtræk auth/RBAC/MFA-modul (§3.3) | 🟠 P1 | Claude |
164: | 8 | Secure-by-default afhænger af TIMELAPSE_ENV-streng (§3.4) | 🟠 P1 | Claude |
165: | 9 | AI Act-screening mangler (§4.1) | 🟡 P2 | Claude (udkast), Peter (beslutning) |
166: | 10 | MFA-enrollment ikke reelt gennemført endnu (§4.2) | 🟡 P2 | Peter/Codex (drift) |
167: | 11 | Repo-hygiejne / dump-filer (§4.3) | 🟡 P2 | Claude (.gitignore + gitleaks-forslag) |
170: | 14 | `Capture` mangler `camera_id` — billedhistorik følger ikke kamera-lokation ved Edge-udskiftning (§2.5) | 🟠 P1 | ✅ Fuldt rettet og backfillet i produktion 2026-07-03: skema v12 + resolver + additivt `camera_id`-filter på `/api/admin/captures` + `headend/tools/backfill_capture_camera_customer.py`, kørt af Peter mod alle 27.662 captures. `camera_id` sat for 965 (de eneste reelt kamera-bundne devices — resten bevidst `NULL`, ikke en fejl). **Åbent:** dedikeret kamera-lokations-UI-side (fuld historik på tværs af Edge-udskiftninger) er ikke bygget — se §2.5 forslag #3 | Claude (kode), Peter (backfill kørt) |
171: | 15 | Tv-overvågningsloven/Databeskyttelsesloven/Arbejdsmiljøloven/RED/CER mangler i DEL 9 (§7) | 🟡 P2 | Claude (udkast), Peter (beslutning) |
172: | 16 | Kryds-kunde-lækage af billeddata ved Edge-gentildeling (R16, fundet under fase 3-implementering) | 🔴 P0 | ✅ Fuldt lukket 2026-07-03: rettet, committet (`bb18421`), deployet, og backfillet — alle 27.662 captures har nu `customer_id` (inkl. et enkelt device, `TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_1`, der manglede kunde-kobling i CMDB og blev rettet undervejs). Ingen rækker afhænger længere af device-fallback'en for tenant-isolation. Se `RISK_ASSESSMENT_v10.md` R16 | Claude (kode+test), Peter (deploy+backfill) |
173: | 17 | `Capture` mangler `site_id` — hierarkiet kunde/site/kamera-lokation var ikke fuldt tagget på billedet (fase 4, rejst af Peter 2026-07-03) | 🟢 P3 | ✅ Fuldt rettet og backfillet i produktion 2026-07-03: skema v13 + resolver udvidet til 3-tuple + backfill-script udvidet + additivt i `/api/admin/captures`-response. Alle 27.662 captures har nu `site_id`. Bevidst KUN tagging — ingen håndhævelse endnu, kræver separat beslutning om at udvide `User`-modellen med site-scope | Claude (kode+test), Peter (deploy+backfill) |
175: Ingen af disse er rettet endnu — dette er bevidst kun observation og rapportering, som aftalt. Jeg foreslår vi tager punkt 1-4 først, da de er små, isolerede rettelser med stor effekt, og fordi 1 og 3 er reelt eksponerede lige nu givet at nginx stadig er public.
179: ## 7. Yderligere lovgivning at have på radaren (ud over AI Act)
183: - **Tv-overvågningsloven (lov om tv-overvågning, DK):** den mest konkrete og oversete. Adskilt fra GDPR — regulerer selve det at opsætte kameraovervågning: skiltningspligt hvor der overvåges, hvem der må overvåge hvad (fx offentligt tilgængelige arealer, indgange, vej/sti forbi byggepladsen), og særlige regler for optagelser der viser personer. Byggepladser grænser ofte op til offentlig vej/sti, så dette bør screenes pr. site, ikke kun GDPR-vurderes. Naturligt at lægge ind i samme DPIA-skabelon som §G/9.7 allerede planlægger.
184: - **Databeskyttelsesloven (DK):** den danske suppleringslov til GDPR — bl.a. regler om behandling af CPR-numre (næppe relevant her) og videre nationale præciseringer. Bør nævnes eksplicit ved siden af GDPR, ikke kun underforstået.
185: - **Arbejdsmiljøloven + Arbejdstilsynets vejledning om kameraovervågning af medarbejdere:** hvis kameraerne fanger egne eller kundens ansatte (ikke kun "byggepladsen"), er der et selvstændigt spor ud over GDPR: legitimt formål, information til de ansatte, og typisk pligt til at inddrage evt. samarbejdsudvalg/tillidsrepræsentant før overvågning af medarbejderes arbejdsindsats sættes op. Det er kundens (den dataansvarliges) pligt over for egne ansatte, men TimeLapse Pro bør have det med i kundevendt vejledning/DPIA-skabelon, så kunderne rent faktisk bliver gjort opmærksomme på det.
186: - **Radioudstyrsdirektivet (RED, 2014/53/EU) + cybersikkerheds-delegeretakt 2022/30/EU:** Edge-hardwaren har WiFi, Bluetooth (BT PAN/TOTP) og 4G-modem — det gør den til radioudstyr under RED, med egen CE-mærkningspligt *uafhængigt af CRA*. Delegeretakten om cybersikkerhed (netværksbeskyttelse, privacy/persondatabeskyttelse, svindelbeskyttelse for radioudstyr) er allerede trådt i kraft og har til dels overlappende, men ikke identiske krav med CRA. Bør tilføjes som eget punkt ved siden af CRA-afsnittet (9.6), da det er let at overse, når man kun tænker "software-CRA".
187: - **CER-direktivet (Critical Entities Resilience):** nævnes i dag kun i forbifarten i `TimeLapse_Security_Compliance_v10.md`'s executive summary, uden eget afsnit — samme gab-mønster som AI Act. Relevans er formentlig lav (I er leverandør, ikke selv en kritisk enhed), men bør have samme korte, eksplicitte vurdering som NIS2 har, i stedet for at stå som et løst navn.
188: - **GDPR Art. 22 (automatiserede afgørelser/profilering)** — nævnes ikke eksplicit i jeres GDPR-afsnit (9.7). Alarm-motoren, der klassificerer "uvedkommende"/hændelser ud fra AI-tags, ligger tæt på automatiseret beslutningstagning, der kan påvirke personer (fx en sikkerhedsreaktion udløst af en algoritmes vurdering). Bør vurderes sammen med AI Act-punktet i §4.1, ikke som en separat proces.
191: - **Bogføringsloven (digitalt bogføringssystem-krav):** ikke et produkt-/databeskyttelsesspørgsmål, men en generel virksomhedspligt for TimeLapse Pro som selskab — nævnes kun for fuldstændighedens skyld, ikke teknisk relevant for platformen.

## Dokumentation/Claude_Observability_ITIM_Design_2026-06-29.md

1: # TimeLapse Pro — Observability / ITIM — Design-notat
13: ## 1. Hvorfor (problem og formål)
20: Det der mangler er **ITIM / observability** — *hvordan har det det lige nu og over tid*:
28: ### Afgrænsning mod de eksisterende lag
32: | Spørgsmål | Hvad skete der (sikkerhed)? | Hvad findes/skal patches? | Hvordan har det det nu + over tid? |
43: ## 2. SABSA-forankring (kort)
60: ## 3. Arkitektur (overblik)
89: **Princip:** ét skrive-API og ét datalag. Collectoren og app-hooks kalder samme interne
95: ## 4. Datamodel (Postgres)
145:     for_seconds   INTEGER      DEFAULT 60,          -- skal holde i X sek før alarm (anti-flap)
168: `1h`-rollup 13 måneder. En intern scheduler-tråd (samme stil som AI-batch-polleren) kører
173: ## 5. Metrik-katalog (de fire scopes)
196: ## 6. API-kontrakt (`/api/itim/*`, RBAC som CMDB/SIEM)
212: ## 7. Alarmering
227: ## 8. Sikkerhed & compliance (designvalg)
240:   "secure-by-default"/"continuous monitoring"-kravene; tilføjes til risk-/krav-registeret.
244: ## 9. Plugin-seam til Elastic (fremtidssikring)
262: ## 10. UI — ny "Drift"-side (Admin-menu)
274: ## 11. Optimerings-fund i eksisterende SIEM/CMDB (foldes ind)
282: 4. **Break-glass checkout** har stadig MFA/IP-whitelist/rate-limit som TODO i koden
283:    (`cmdb.checkout_break_glass`) — reelt SABSA-/compliance-hul; bør lukkes (egen lille opgave).
289: ## 12. Rollout-plan og arbejdsdeling
299: **Afhængigheder/risici:** `psutil` skal i venv (let); volumen-skrivetest må ikke selv ligge på
301: omvendt netop *er* signalet, så vi måler "mounted/writable" separat fra latens). Collectoren skal
306: ## 13. Åbne spørgsmål til Peter — AFGJORT af implementeringen (opdateret 2026-07-05, periodisk tjek #45)

## Dokumentation/Claude_QA_Arkitektur_Review_2026-07-15.md

1: # Claude — QA- & Arkitektur-review efter z.ai-perioden
9: ## 1. Kritiske fund (bør handles på nu)
11: ### 1.1 🔴 SEC: `/api/ai/vocabulary/*` og AI-review-endpoints er HELT uden authentication
19: ### 1.2 🔴 BUG: `get_similar_tag_suggestions` crasher altid (TypeError)
22: ### 1.3 🟠 Ucommittet z.ai-arbejde ligger i working tree
27: - Settings-nøglen `peter-vil-gerne-lege-med-ollama` som produktions-feature-flag bør omdøbes (fx `openwebui_enabled`) før commit.
30: **Anbefaling:** Beslut commit/ret/kassér i fællesskab. Indtil da: lad filerne ligge (evidens).
32: ### 1.4 🟠 CI gate'r kun 3 af 40 testfiler
33: `ci.yml` kører kun `test_agent_integrity.py`, `test_headend_endpoints.py` og smoke-suiten. `tests/` har 40 filer, og HANDOVER_LOG (2026-07-13) dokumenterer **36 fejlende tests** (rate limiting, nginx config, node-agent) der bare står og fejler uden at blokere noget. Fejlende tests der ikke gate'r er værre end ingen tests — de lærer alle at ignorere rød. **Anbefaling:** (1) triager de 36: fix, markér `xfail` med issue-reference, eller slet; (2) udvid CI til hele suiten med en kendt-grøn baseline; (3) indfør samme ratchet-princip som ESLint-gaten (H-02).
37: ## 2. Kodekvalitet — småfejl og mønstre (ruff + manuel læsning)
47: | `B023` loop-variabel i closure | 3 (bl.a. `gemini_service.py:726`) | Klassisk sen-binding-bug; virker måske tilfældigt nu. |
55: ## 3. Teknisk gæld — status og retning fremad
57: ### 3.1 Gælden VOKSER
58: Målt mod TEKNISK GÆLD-analysen (2026-07-06) og P2-01-planen (2026-07-07):
70: ### 3.2 Retningsregler fra nu af (forslag til fælles vedtagelse)
71: Det rigtige tidspunkt at sætte retningen er nu — foreslås som bindende arbejdsregler i CLAUDE.md/AGENTS-instruktioner, så både Claude, Codex og fremtidige AI-sessioner er underlagt dem:
74: 2. **Boy scout-reglen, afgrænset:** Rør du en funktion >125 linjer, skal den deles op i validation → execution → response (jf. gæld-analysens §2) i samme PR — men refaktorér aldrig utestet kode uden først at skrive en kontrakttest (H-05-mønsteret).
78: 6. **TODO-markører med ID** (`# TODO(P2-01): ...`) som gæld-analysen foreslog — plus et ugentligt greb: `grep -rn "TODO(" | wc -l` rapporteres i SYSTEM_HEALTH_REGISTER.
81: ### 3.3 P2-01 eksekvering (konkretisering af eksisterende plan)
86: ## 4. Arkitektur: fra Timelapse-produkt til generisk edge-platform
88: ### 4.1 Det strategiske snit: Platform vs. Payload
101: **Anbefaling:** Definér et payload-interface i edge-agenten (fx `PayloadDriver`: `configure(cfg)`, `tick(now)`, `collect_telemetry()`, `handle_command(cmd)`), og flyt gphoto2/capture-logikken ind bag det som første implementation. `_lab_tick`-oprydningen (3.1) er den naturlige anledning. På headend-siden svarer det til at holde capture/AI-domænet ude af platform-modulerne under P2-01. **Navngivningen** i DB/API bør samtidig gøres payload-neutral hvor det er gratis (fx "asset" frem for "camera" i nye platform-tabeller — men omdøb ikke eksisterende, jf. additiv-princippet).
103: ### 4.2 Zoner og DMZ (IEC 62443-terminologi: zones & conduits)
104: Nuværende lab-setup har alt (nginx, FastAPI, Postgres, Ollama, billeder, UI) i én zone på én maskine. Mod prod bør målbilledet være:
108: | **Z1 DMZ / præsentation** | nginx (TLS-terminering, 8443, DNS-01), statisk UI-build, rate limiting, fail2ban, WAF-regler | Internet |
114: Konkret og realistisk på nuværende hardware: zonerne behøver ikke separate maskiner fra dag 1 — start med **logisk** adskillelse (separate nginx-vhosts/porte, separate DB-roller med least privilege pr. modul, UI serveret som ren statisk DMZ-artefakt uden API-nøgler) og dokumentér conduits i SABSA_Architecture_v10. Det gør den fysiske udskilning (staging/prod jf. MILJOE_ARKITEKTUR v1) til et deployment-valg, ikke en omskrivning. Vigtigt eksisterende princip der SKAL bevares i platformen: **edge initierer alle forbindelser** (ingen indgående forbindelser til edge) — det er netop det mønster, der gør "sikker remote access via edgen til backendsystemer" muligt for de nye verticals: fjernadgang sker via edge'ens udgående tunnel + AccessTicket/break-glass-modellen (design 2026-07-06), aldrig ved at åbne porte på OT-nettet.
116: ### 4.3 Frontend/backend
121: ## 5. Dokumentation — er 00_START_HER/HANDOVER_LOG dækkende?
123: 1. **To dokumentationstræer:** z.ai-perioden har skabt ~20 dokumenter i `docs/` (drift-mode, poll-analyser, site-look, edge-arkitektur, LAB-testguide m.m.), men `00_START_HER.md` nævner kun `Dokumentation/`. En ny session finder dem ikke. **Anbefaling:** Beslut ét hjem (forslag: flyt varige dokumenter til `Dokumentation/`, lad `docs/` være til kode-nære udviklernoter) og tilføj en linje om det i 00_START_HER §6.
127: 5. **Handover-kvalitet fra z.ai-perioden:** Entries er formkorrekte, men statusudsagn skal læses kritisk — fx "Status: Klar til produktion!" (07-13) om ændringer, der aldrig var kørt på device, og "36 tests failed — ikke vores kode" uden triage. Faktuelt korrekte hvad-blev-ændret-lister, overoptimistiske konklusioner. Det bekræfter Peters mistanke: gennemgå z.ai-periodens commits med kontrakttests frem for at stole på log-konklusionerne.
132: ## 6. Prioriteret handlingsliste
136: | 1 | SEC-015: Auth på vocab-/review-routere + automatisk route-auth-test | Codex el. Claude | Timer |
138: | 3 | Beslut skæbne for ucommittet Open WebUI-arbejde (ret 1.3-punkterne før commit) | Peter + én agent | Timer |
145: | 10 | SABSA_Architecture_v10: tilføj zone/conduit-målbillede (§4.2) | Claude | Timer |

## Dokumentation/Claude_QA_Review_2026-07-17.md

1: # Claude — QA-opfølgning & retningsnotat
9: ## 1. Hvad er lukket siden 15/7-reviewet (anerkendelse)
15: | R22 vocab/review uden auth | ✅ `vocab_read_router` (viewer) / `vocab_router` + `_rev_router` (super_admin) — korrekt splittet |
16: | R23 `_normalize_tag_for_similarity` self-bug | ✅ Rettet |
17: | R24 `/translations` 403-regression | ✅ Viewer-adgang genoprettet |
18: | R25 MFA-disable uden step-up | ✅ Step-up + SIEM-events |
19: | Route-auth sweep (K1) | ✅ `headend/tests/test_route_auth_coverage.py` — solid: rekursiv dependency-inspektion, eksplicit exception-liste med begrundelser, high-risk-matrix |
20: | Bare `except:` | ✅ 0 i egen kode (headend/edge/node-agent) |
21: | `main_endpoints.py` (død patch-skabelon) | ✅ Slettet |
22: | JWT-secret divergens main/redaction | ✅ Fail-fast i prod (<32 tegn afvises); redaction delegerer til central auth |
23: | CI kun 3 testfiler | ✅ Fuld `not integration`-suite + py_compile + shell-check; symlinks gjort relative |
24: | Brudte absolutte symlinks deploy/backup.sh | ✅ Relative nu |
25: | GRC-register (nyt siden) | ✅ Gennemlæst `grc_register_api.py` (380 linjer): auth på ALLE endpoints, super_admin-krav på dokumentgodkendelse, hashbar evidens, snapshot-baseret revisionsidentitet. Godt håndværk. |
31: ## 2. Nye fund (ikke tidligere dokumenteret)
33: ### 2.1 🔴 SEC-016 (forslag): Fabriksstandard BT PAN TOTP-secret — universel default credential
39: - **Compliance:** CRA Annex I §1(1) forbyder udlevering med kendte udnyttelige default-credentials; IEC 62443-4-2 CR 1.5 (authenticator management) og NIS2 art. 21 rammes også. Dette skal lukkes før CE-mærkning under CRA overhovedet kan diskuteres.
48: ### 2.2 🟠 GOV-01: Ratchet-baseline blev HÆVET — governance-mekanismen holdt ikke ved første tryk
50: `tests/architecture_baseline.json` blev i commit `fc3e58b8` (2026-07-16) hævet fra `18483` → `18549` (+66 linjer), samtidig med at main.py voksede tilsvarende. Ratchet-reglen (K3: "baseline må kun sænkes efter udtrækning") blev altså omgået ved at flytte loftet — netop det, ratchets skal forhindre. Ingen undtagelse er dokumenteret i commit eller handover.
56: ### 2.3 🟠 R09: Backup-default stadig i stykker (gentagelse — nu 2. påmindelse)
58: `deploy/scripts/backup.sh` linje 26 har fortsat `BACKUP_BASE="${BACKUP_BASE:-/Volumes/data-fast}"` — volumen-roden er ikke skrivbar for `peter`, så backup fejler med default-indstillinger (manifesteret 2026-07-16, jf. handover). Scriptet er korrekt fail-closed (`set -euo pipefail`), men **default-konfigurationen producerer ingen backups**. Handover 07-16 bad Codex fikse det; det er endnu ikke sket. R09/P0-03 er fortsat go-live-blocker uden grøn restore-evidens.
60: ### 2.4 🟡 Oprydningsrestancer fra 15/7-handlingslisten (punkt 5 og 7 — ikke udført)
64: - **`docs/` vs `Dokumentation/`:** de 20 z.ai-dokumenter i `docs/` er stadig ukendte for 00_START_HER (beslutning udestår).
65: - **`ISSUES.md`** er stadig dateret 2026-06-14 og lister A-01..03 som åbne, selvom de er lukket. Bør have en forældelses-banner eller flyttes til `Gamle versioner/` — nu hvor GRC-registret i PostgreSQL er autoritativt, er dokumentet dobbelt farligt.
69: ### 2.5 🟡 Cirkulær import-workaround spreder sig som mønster
71: De nye API-moduler (`grc_register_api.py`, `storage_api.py`, m.fl.) bruger alle `from main import get_current_user` **inde i funktionskroppen** for at undgå cirkulær import. Det virker, men cementerer main.py som nav: hvert nyt modul binder sig runtime til monolitten. Det er det stærkeste tekniske argument for at **P2-01 sprint 1 = udtræk af auth/RBAC-modulet** (`headend/platform/auth.py` e.l.): derefter kan alle routere importere auth rent, og mønsteret forsvinder af sig selv. Bemærk også at de nye moduler bruger rå `payload: dict` frem for Pydantic-modeller — acceptabelt for interne admin-API'er, men Pydantic bør være husstandarden ved udtræk.
73: ### 2.6 Målinger (gælden pr. i dag)
79: | Direkte routes i main.py | — | 235 | **235** (ratchet holder ✅) |
82: | UI-sider >1.200 linjer | — | 4 | **7** (BackupPage 2.016 er størst) |
88: ## 3. Teknisk gæld — retningen fra nu af (svar på Peters spørgsmål 2)
90: Retningen ER sat — ADR-001 + K1-K6 er de rigtige regler, og §1 viser at de efterleves af agenterne. Det der mangler er ikke flere regler, men **eksekvering og to justeringer**:
94: 3. **Gældsbudget frem for gældsstop:** enhver session, der rører main.py, skal efterlade den mindre end den fandt den (netto-linjer). Det er boy scout-reglen gjort målbar — og den håndhæves allerede af ratchet'en, hvis baseline sænkes løbende.
96: 5. **TODO(ID)-markører:** kun 9 findes i dag. Ved hvert fund der udskydes: markér i koden med GRC-ID, så gælden er synlig hvor den bor (og nu sporbar i PostgreSQL-registret).
102: ## 4. Modularisering mod generisk edge-platform (svar på Peters spørgsmål 1)
106: Gap-analyse — hvad der konkret mangler mellem beslutning og virkelighed:
108: | Gap | Status | Næste skridt |
110: | `contracts/` (PayloadDriver + manifest-schema) | Findes ikke endnu | **Fase 1-spike:** definér kontrakten og wrap nuværende kameralogik bagom — anledningen er `_lab_tick`-oprydningen (457 linjer, R26). Beviser kontrakten passer, før noget flyttes. |
116: **Om sikker remote access til OT-backends** (vandværkets SRO/PLC, møllens styring): mønsteret findes allerede i produktet — edge initierer alle forbindelser, reverse tunnel + AccessTicket/break-glass (R19, Support Access Model 2026-07-06, Intern CA/mTLS-design 2026-07-05). Det, der gør det OT-klart, er allerede normativt i ADR-001 §6/amendment 5: JIT-tickets, destinations-/port-allowlist, kortlivede certifikater, session recording, kill switch, kundegodkendelse. Min tilføjelse: når første OT-vertical bygges (Fase 4), skal conduit'en ind i zone/conduit-registret med **SL-T pr. zone** og en eksplicit dataklassifikation (procesdata ≠ billeddata — andre retention- og integritetskrav; for et vandværk er integritet/availability vigtigere end confidentiality, omvendt af timelapse-billeder). Det er dokumentarbejde oven på eksisterende mekanik — ikke ny kode.
118: **Skalérbarhedsbekymring at holde øje med:** headend-monolitten er i dag også *platformens* headend. Når payloads bliver flere, må headend-siden følge samme snit (platform-API vs. payload-API som separate routere/moduler) — det er allerede planens Fase 2/3, blot værd at fastholde ved hvert udtræk: **spørg "platform eller payload?" ved hver eneste modul-udtrækning** (afgrænsningstesten i ADR-001: ville modulet se identisk ud for et vandværk?).
122: ## 5. Dokumentation — er 00_START_HER + HANDOVER_LOG dækkende?
124: 00_START_HER.md bootede denne session korrekt — kernefakta, ADR-binding og GRC-banneret er præcis det en ny session skal bruge. Jeg har lavet følgende **additive** rettelser i dag: opdateret "Sidst opdateret", tilføjet manglende pointere (PRIORITIZED_BACKLOG, MASTER_TEST_CHECKLIST, teknisk gæld-analysen, P2-01-planen, 15/7-reviewene + dette dokument, STAGING_TIL_PROD_PROMOTION, HEADEND_GENERATOR), markeret ISSUES.md som forældet, og tilføjet en note om `docs/`-mappen og om governance-gates' placering i koden.
127: 1. **HANDOVER_LOG-rotation** (779 KB + dobbelt indsættelsespunkt, jf. 2.4) — jeg foreslår at gøre det, men rører ikke strukturen uden ok.
133: ## 6. Prioriteret handlingsliste
137: | 1 | SEC-016: per-device BT TOTP-secret, fjern factory-default fail-open (2.1) + GRC-entry | Codex (kode) + Claude (SEC-doc) | 🔴 P0 (CRA-blocker) |
138: | 2 | R09: ret `BACKUP_BASE`-default + grøn restore-evidens (2.3) | Codex | 🔴 P0 (go-live-blocker, 2. påmindelse) |
139: | 3 | GOV-01: vedtag ratchet-undtagelsesregel + betal 66 linjer tilbage (2.2) | Peter (regel) + første udtræk | 🟠 P1 |
140: | 4 | P2-01 sprint 1: udtræk auth/RBAC-modul med kontrakttests (§3.2 + 2.5) | Claude + Codex review | 🟠 P1 |
141: | 5 | Fase 1-spike: `contracts/PayloadDriver` + wrap kameralogik (§4) | Claude design + Codex impl. | 🟠 P1 |
142: | 6 | ADR-002 (pakkeformat/signering/sandbox) + zone/conduit-register | Claude, review af alle | 🟡 P2 |
143: | 7 | Oprydning: apply_*_patch.py, .bak-filer, F401/E402, tracked .bak (2.4) | Hvem der først har ledig time | 🟡 P2 |
144: | 8 | Dokumentbeslutninger: HANDOVER-rotation, docs/, ISSUES.md (§5) | Peter | 🟡 P2 |
145: | 9 | Gældsmetrikker i SYSTEM_HEALTH_REGISTER (§3.4) | Claude | 🟡 P2 |

## Dokumentation/Claude_REVIEW_Generatorer_Edge_Headend_2026-07-17.md

1: # Claude — Review af Edge- og Headend-generatorerne (med CrushFTP-sameksistens)
9: ## 1. Samlet vurdering
15: ## 2. Headend-generatoren — hvad virker
22: | Enroll (Fase 3) | Fail-closed: bootstrap-token fra fil (aldrig som argument), `node_type=headend` → `KeyCredential(entity_type="headend")` (verificeret i `enroll_device`), venter på autentificeret inventory-kvittering, ellers non-zero exit. Node-agent-installeren kræver eksplicitte `--device-id/--headend-url/--api-token-file` — ingen R&D-defaults tilbage. ✅ HEADEND_GENERATOR §8 punkt 1-3 bekræftet implementeret. |
26: ## 3. Fund — sameksistens-huller (vigtigst først)
28: ### 3.1 🔴 GEN-01: SFTP-ingress (22222) er slet ikke en del af headend-generatoren
38: ### 3.2 🔴 GEN-02: `sftp_port`-default er **22** — kollisionskurs med CrushFTP
42: **Anbefaling:** (1) skift kode-defaulten til `22222` (PORTS.md er policy — koden bør følge den), (2) lad install_headend.sh seede `sftp_host`/`sftp_port`/`sftp_remote_base`-settings i DB, (3) tilføj kontrakttest: config-hierarkiets sftp.port må aldrig være 21/22/80/443. Bemærk også at `backup_sftp`-blokken har samme hardcodede `"port": 22`-default.
44: ### 3.3 🟠 GEN-03: Reverse-tunnel-indgangen er udefineret på staging/prod
46: `edge/tunnel/ssh_manager.py:300`: SSH-endpoint-fallback er port **22**. På R&D virker det (macOS Remote Login på 22), men på staging/prod ejer CrushFTP/system-SSH port 22, og generatoren opsætter hverken tunnel-bruger, authorized_keys eller port. Hardening-profilen siger selv "Human/admin SSH and reverse-debug tunnels must be configured separately" — men ingen definerer *hvor*.
50: ### 3.4 🟠 GEN-04: Tunnel-port-allokatoren kan tildele 2222 (reserveret)
54: ### 3.5 🟠 GEN-05: Dokument-modstrid om SFTP-opsætning (v10 vs hardening-profil)
58: ### 3.6 🟡 GEN-06: Release-disciplin-hul i Fase 2
60: `example-{staging,prod}.conf` sætter `TL_REPO_DIR=/Users/peter/projects/timelapse-pro`, men Fase 1 staged den verificerede release i `--destination` (fx `~/tl-staging-release`). Hvis Peter følger example-conf'en ordret, installeres der fra en almindelig arbejdskopi — udenom GPG-verifikationen. **Anbefaling:** example-confs skal pege `TL_REPO_DIR` på staged-release-mappen, og install_headend.sh bør advare hvis `TL_REPO_DIR` er et git-checkout med dirty tree/uden verificeret tag.
62: ### 3.7 🟡 GEN-07: `admin/changeme`-vinduet på offentlig 8443
66: ### 3.8 🟡 GEN-08: Enroll mod `https://127.0.0.1:8443` fejler på certifikat
68: `enroll_headend_cmdb.sh` kræver `https://` (godt), men HEADEND_GENERATOR §4 foreslår `HEADEND_URL=https://127.0.0.1:8443` — LE-certifikatet dækker kun domænet, så urllib fejler TLS-verifikation mod 127.0.0.1. **Anbefaling:** brug altid det rigtige backend-domæne i enroll/agent-URL (manualen gør det), eller tilføj eksplicit CA-/hostname-håndtering.
72: ## 4. Fund — edge-generatoren
74: ### 4.1 🟠 GEN-09: Device-SSH-privatnøgler genereres centralt, ligger i klartekst i DB og bages ind i image
78: ### 4.2 🟡 GEN-10: `_headend_api_url`-fallback er `http://127.0.0.1:8000/api`
80: Hvis hverken settings eller env er sat på en ny headend, genereres bootstrap.yaml/images med en ubrugelig localhost-URL — stille fejl frem for fail-fast. Lav risiko i praksis (install_headend.sh sætter `BASE_URL`), men provisioning bør nægte at generere med localhost-URL når `TIMELAPSE_ENV=staging|prod`.
82: ### 4.3 🟡 GEN-11: Hvor bygges edge-images til prod? (beslutning mangler)
84: Flashable-build kræver Docker buildx på den headend hvor provisioneringen kører. Skal prod-headenden selv kunne generere edges (⇒ Docker + build-toolchain skal hærdes og præinstalleres på prod), eller bygges rootfs på R&D og promoveres som signeret artifact, mens prod kun laver injection (token/nøgler/WiFi)? Promotion-metodikken dækker ikke edge-images i dag. **Anbefaling:** afgør i promotion-sporet; indtil da dokumenterer manualen Docker-kravet eksplicit.
86: ### 4.4 ✅ Positivt
92: ## 5. Sameksistens-facit (CrushFTP)
96: | UI/API (nginx, TLS) | 8443 | ✅ Sikkert: preflight + install afviser 21/22/80/443 hårdt; DNS-01 rører ingen port |
97: | Certifikat | (ingen) | ✅ DNS-01 — uafhængig af CrushFTP's 80/443 |
98: | SFTP-upload fra edge | 22222 | 🔴 Mekanik findes, men intet generator-trin (GEN-01) OG kode-default peger på 22 (GEN-02) |
99: | Reverse SSH-tunnel | ? | 🟠 Udefineret; edge-fallback er 22 (GEN-03) |
100: | Tunnel-portallokering | 2201+ | 🟠 Kan ramme reserveret 2222 (GEN-04) |
101: | Marketingsite | — | ✅ Hostes bevidst separat (ingen konflikt) |
102: | Syslog | 5514 | ✅ Ikke-privilegeret, konfliktfri |
106: ## 6. Nye dokumenter skrevet i dag
111: ## 7. Handlingsliste
115: | 1 | GEN-02: kode-default `sftp_port` 22→22222 + seed settings i install + kontrakttest | Codex | 🔴 Før staging-install |
116: | 2 | GEN-01: SFTP-ingress som scriptet Fase 2b (genbrug deploy/ssh/-profilen) | Codex | 🔴 Før staging-install |
117: | 3 | GEN-03: Beslut tunnel-ingress-port for staging/prod | **Peter** | 🟠 Beslutning |
118: | 4 | GEN-04: Port-allokator: reserved-exclusion + range | Codex | 🟠 |
119: | 5 | GEN-05/GEN-06: docs-rettelser (v10 §12, example-confs) | Claude | 🟡 |
120: | 6 | GEN-09: image-som-hemmelighed-regel nu; device-genereret nøgle på sigt | Claude (doc) + Codex (kode) | 🟠 |
121: | 7 | GEN-11: Beslut build-sted for prod-edge-images | **Peter** (promotion-sporet) | 🟡 Beslutning |

## Dokumentation/Claude_Support_Access_Model_2026-07-06.md

1: # TimeLapse Pro — Kontrolleret Support-adgang til Staging/Prod (Break-Glass-model)
17: ## 1. Baggrund og formål
24: 2026-07-06 uddybede Peter dette: "Jeg tænker vi (trods min tidligere udtalelse) skal have en
26: forbindelse med installation og fejlsøgning/fejlretning. Det skal selvfølgelig være dokumenteret
42:    accept/afvisning (implicit eller per-case), udløb fastsættes som en del af selve aktiveringen,
47: ## 2. SABSA-forankring (kort)
51: | **Kontekstuelt** (forretning) | Peter skal kunne få agent-hjælp til installation/fejlsøgning på staging/prod uden at opgive den kontrol og det kundetillids-løfte, der lå i den oprindelige "aldrig nogensinde"-politik. |
55: | **Komponent** | `ssh-keygen -s` (SSH-certifikat-udstedelse, indbygget i OpenSSH — ingen ny afhængighed), `sshd_config TrustedUserCAKeys`, samme GPG-signeringsmønster som `ChangeTicket` (`content_sha256`+`signature`+`signed_by`). |
65: ## 3. Princip: default-deny + kontrolleret undtagelse
81: ## 4. Hvorfor en SEPARAT Support-CA (ikke device-CA'en fra #52)
88:   kompromitteret device-signeringsnøgle bør aldrig kunne bruges til at udstede en
91:   serveren) og bør derfor have adskilte nøgler, adskilte udstedelsesprocedurer og adskilte
94:   (§4.3 i CA/mTLS-designet) — det modsatte af, hvad en support-adgangsmekanisme skal have (timer,
104: ## 5. Teknisk mekanisme — SSH-certifikater med indbygget, kryptografisk udløb
111: igen. Dette matcher direkte Peters krav om at "udløb markeres som en del af aktiveringen".
113: **Foreslået flow (skitse, kode IKKE skrevet):**
115: 1. **Behov opstår** — Peter skal have agent-hjælp til installation eller fejlsøgning på en
124:    tjek (hvilken kunde, hvilken hjemmel, ja/nej) skal stå i selve ticketen (§6), ikke kun huskes.
137:    certifikat — ingen manuel oprydning nødvendig. `sshd_config` på staging/prod skal have
139: 6. **Tidlig tilbagekaldelse** (før udløb, fx hvis sessionen afsluttes tidligere end planlagt):
147: ## 6. Signeret ticket og audit-log
180:    adgangstildeling. Omvendt mangler `ChangeTicket` alle §6-adgangsfelterne (`agent`, `machine`,
194: 3. **Konsistent med §4's eget separations-princip.** §4 begrunder allerede en SEPARAT Support-CA
198:    ("hvem må se support-adgangs-historik vs. deployment-historik") skal styres pr. række i stedet
201: `ticket_id`-navnerummet og GPG-signeringsmønsteret (`content_sha256`+`signature`+`signed_by`) bør
202: stadig genbruges på tværs af begge tabeller — kun selve tabelstrukturen bør holdes adskilt. Dette
207: gyldighedsvinduet bør ende i den eksisterende SIEM/syslog-modtager (`dk.froekjaer.timelapse-syslog`,
213: ## 7. Forhold til den eksisterende permanente politik
228: ## 8. Hvad der IKKE er besluttet/bygget endnu
239:   det"-konflikt, men det bør skrives og gennemgås grundigt før første brug, givet emnet.
244:   fremtidig forbedring, ikke en blocker for selve adgangsmodellen.
247:   modsatte formål (en kontrolleret VEJ til midlertidig adgang) — de to bør designes til at
258:   faktiske eksekveringsmiljø) om SSH-forbindelsen overhovedet kan etableres. Hvis ikke, skal §5
262:   Codex' eksekveringsmiljø har bredere netværksadgang — bør afklares pr. agent, ikke antages fælles.
266: ## 9. Dokumenthistorik
272: | 2026-07-06 (periodisk tjek #80) | Claude: besvarede §6/§8's åbne AccessTicket-skema-spørgsmål med en kodebaseret anbefaling (separat `access_tickets`-tabel) efter faktisk læsning af `headend/database.py` (`ChangeTicket`-model) og `ChangeTicketsPage.tsx` (status-UI-logik) — tre konkrete tekniske fund (feltmisforhold, inkompatibelt status-vokabular, UI/RBAC-kobling), ikke kun abstrakt afvejning. Rådgivning, ikke beslutning — ingen kode/migration skrevet. |

## Dokumentation/Claude_TEST_AUDIT_2026-07-18.md

1: # Uafhængig test-audit — TimeLapse Pro
7: ## 1. Hovedkonklusion (læs denne)
11: GRC-registeret indeholder **rammen**: de kanoniske testporte (10 test-items), 16 fund, 174 krav, 27 risici og den accepterede ADR-001. Men **selve testudførelsen** — de ~1.175 faktiske testkørsler den sidste uge — ligger stadig i `UI_TESTJOURNAL_v1.md`, `MASTER_TEST_CHECKLIST_v1.md`, `HANDOVER_LOG.md` og CI-runs, **ikke** som individuelle runs i GRC. Før min audit havde GRC kun **3 registrerede test-runs**, selvom Codex reelt har kørt 544 integrationstests + 631 unit-tests + 27 UI-routes + ~40 funktionelle UI-cases.
15: **Samlet vurdering af hvor godt det går:** grønt på det funktionelle kernesystem (auth/RBAC, UI-render, update-flow E2E, integrationsmatrix indsamlet og kørende). Én reel rød test (Nginx-portsameksistens) og en håndfuld ægte huller, som næsten alle er sprunget over af **legitime, dokumenterede årsager** — hardware, destruktiv testdata, eller en kendt blocker. Ikke noget der ser ud til at være "glemt".
19: ## 2. Hvad GRC-registeret faktisk indeholder (pr. 2026-07-18, efter min registrering)
23: | Krav (requirement) | 174 | 96 funktionelle + 77 non-funktionelle (Codex' import 07-17) |
24: | Risici (risk) | 27 | R01-R27, historisk state i `candidate_review` |
25: | Test-items | 10 | 3 verified, 1 blocked, 1 fail, 5 not_run |
28: | Action / Control | 1 / 1 | ACT-TEST-001 (closed), ADR-001 (accepted) |
30: ### De 10 kanoniske test-items
34: | TV-001 | ✅ verified | P0 | CI-identisk unit/contract-gate |
35: | UI-ROUTES-001 | ✅ verified | P0 | Alle beskyttede UI-routes renderer uden 500/login-loop |
36: | TV-GEN-01 | ✅ verified | P1 | Headend-generator (mine tests — tilføjet i denne audit) |
37: | IT-G2 | 🚧 blocked | P0 | Auth/RBAC-integrationstest i isoleret DB |
38: | IT-MATRIX-544 | 🔴 fail | P0 | Komplet integrationsmatrix (1 reel FAIL, se §4) |
40: | UI-UPD-06 | ⬜ not_run | P0 | Signeret offline Edge OS-update E2E |
41: | UI-UPD-07 | ⬜ not_run | P1 | Signeret Edge app-rollback E2E |
42: | UI-UPD-08 | ⬜ not_run | P1 | Ollama-update gennem headend |
47: ## 3. Hvad der FAKTISK er testet (bredden, fra dokumenterne)
63: ## 4. Den ene røde test — og hvorfor den betyder noget
65: **IT-MATRIX-544 / UI-journal 2026-07-18:** Den aktive R&D-Nginx binder stadig **80/443**, ikke den besluttede **8443**. Det er den eneste reelle FAIL i hele matricen. Den er vigtig, fordi det er præcis den **CrushFTP-sameksistens** vi behandlede i generator-reviewet (GEN-serien): på R&D er der ingen CrushFTP, så 80/443 virker — men testen håndhæver korrekt målbilledet, og den vil blokere staging/prod go-live indtil porten flyttes. Status i GRC: åben, korrekt dokumenteret. **Ikke** et overset problem.
69: ## 5. Hvad mangler — og den ærlige årsag til at det er sprunget over
75: | PROC-BKP-01 (backup+restore) | not_run P0 | **Blokeret af en ægte bug (R09):** `backup.sh` default `BACKUP_BASE` peger på den ikke-skrivbare volumen-rod → backup kører ikke med defaults. Man kan ikke restore-teste en backup der ikke laves. Skal fixes før testen kan køre. |
76: | IT-MATRIX-544 (nginx-port) | fail P0 | **Miljø/beslutning:** R&D kører bevidst 80/443; kræver portmigration til 8443 (CrushFTP-sameksistens). Go-live-blocker. |
78: | UI-UPD-06/07/09 (offline OS-update, rollback) | not_run/NOT RUN | **Kræver kontrolleret fysisk R&D-Edge** + destruktiv rollback — må ikke køres ad hoc. Offline-bundle-delen (#91) ER dog kørt. |
79: | LAB/kamera write (UI-124..128) | not_run | **Kræver fysisk Nikon Z30** i LAB-flow (fokus, live stream, capture). Hardware-afhængighed. |
80: | GDPR redaction/retention/sletning (UI-304..306) | not_run | **Destruktivt + kræver afgrænset ægte billeddata** med audit/rollback. Bevidst ikke kørt uden godkendt testdata. |
81: | MFA enrollment (UI-107) / WebAuthn (UI-108) | not_run/blocked | **Kræver afgrænset QA-bruger / kompatibel authenticator.** |
82: | IT-G2 (auth i isoleret DB) | blocked P0 | **Isolations-infra var umoden** — men delvist løst nu (isoleret headend på :18080/:8011 er taget i brug). Bør kunne unblockes. |
85: **Er manglerne dokumenteret?** Ja — konsekvent. Både UI-journalen (§9 exit-kriterier), MASTER_TEST_CHECKLIST (§9 manglende tests) og GRC-status flagger dem. Det er faktisk et af projektets stærkeste punkter: der er ikke fundet et eneste hul, som ikke allerede var kendt og nedskrevet et sted. Problemet er ikke skjulte mangler — det er at evidensen ligger spredt.
89: ## 6. Hvad jeg ændrede i GRC under denne audit
100: ## 7. Anbefalinger (prioriteret)
110: ## 8. Bundlinje
112: Systemet er **godt testet og ærligt dokumenteret.** Det funktionelle kernesystem er grønt; de non-funktionelle huller er få, kendte og har legitime årsager (hardware, destruktiv data, én ægte bug, kode-der-ikke-er-bygget-endnu). Der er **ingen tegn på skjulte eller glemte mangler.** Den reelle svaghed er sporbarhed: GRC er den autoritative ramme, men testudførelsen lever stadig i dokumenterne — og de to bør bygges tættere sammen, før GRC kan bære "single source of truth"-titlen fuldt ud.

## Dokumentation/Claude_Update_Flow_Review_2026-08-16.md

1: # Claude — Gennemgang af opdateringsflowet (Edge + Headend) (2026-08-16)
8: **Provenance-note (jf. TRUST.md/EVIDENCE_MODEL.md):** AI-genereret evidens, ikke en autoritativ konklusion. Skal efterprøves af et menneske før den lægges til grund for beslutninger. Bygger videre på [Claude-2026-08-15.md](Claude-2026-08-15.md) og anvender samme metode (kode-mod-påstand-verifikation).
12: ## Kort svar
18: **Er det brugervenligt?** Grunddesignet og tooltip-teksten er god, men den mindst friktionsfyldte handling ("Godkend") er også den med størst konsekvens ("Alle enheder"), uden ekstra advarsel.
22: ## 1. Kritisk fund: signaturverifikation på edge er ikke reel
34: ## 2. Governance-bypass: den tiltænkte, gennemgåede sti bliver reelt ikke brugt
36: To måder en OS-opdatering kan opstå på, med modsat tillidsmodel — begge indført i samme commit (`b3666709`, 2026-06-14):
41: | `headend/main.py` (`os_security_ignored_cmdb_catalog_required`) | Kræver manuelt admin-trigger (`os-catalog/refresh-from-builder`/`import-apt-list`), opretter `blocked`-update | Ja (tiltænkt) |
47: ## 3. Status på kendte issues (ISSUES.md E-01/E-02, juni 2026)
51: | E-01 "build_os_bundle.py køres aldrig" | 🟡 Delvist løst | Auto-poller virker reelt — men kun for den uverificerede sti (§2), ikke den tiltænkte lab-gatede sti |
52: | E-02 "hele flowet er ikke testet ende-til-ende" | 🔴 Stadig åbent | `tests/test_os_offline_update.py` tjekker kun at scripts *findes* og indeholder bestemte strenge (fx `"gpg" in content.lower()`) — ingen test kører den faktiske kæde byg → signér → download → verificér → installér → rapportér |
54: ## 4. Rollback er asymmetrisk og delvist ufuldstændig
61: ## 5. Headends egen deployment
71: ## 6. UI/UX for operatøren (`UpdatesPage.tsx`)
76: - **"Godkend"** kræver samme ene modal og samme knapstyling uanset scope — at vælge "Alle enheder" (`:1771`) giver ingen ekstra advarsel eller preview af hvor mange devices der rammes (`:1809-1815`).
77: - **"Afvis"** har ingen bekræftelse overhovedet (`:740-745`).
80: - `DeviceUpdateMatrix` linker ikke til den specifikke update-række — operatøren skal matche ID'er visuelt (`:960-965`).
84: ## Anbefalinger, prioriteret
86: 1. **Vigtigst:** beslut bevidst om edge-signaturverifikation skal være reel (faktisk OpenPGP/signaturtjek), eller om den nuværende model ("stol på den autenticerede headend-session") er en accepteret, dokumenteret risiko. Lige nu er det en udokumenteret afvigelse fra det designet selv hævder.
91: 6. UI: skalér bekræftelses-friktion til blast radius (advarsel/preview ved "alle enheder"), og oversæt fejlkoder til de forklaringer der allerede findes i dokumentationen.
95: *Denne rapport er genereret af Claude (Sonnet 5) ved AI-assisteret kodegennemgang. Materiel AI-involvering er hermed synliggjort jf. framework'ets Provenance-krav. Konklusioner bør efterprøves af et menneske før de lægges til grund for beslutninger.*

