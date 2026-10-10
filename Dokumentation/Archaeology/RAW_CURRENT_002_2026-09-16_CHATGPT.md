# Raw archaeology extract — current 002

## Dokumentation/AI_KOMPETENCER_OG_OPGAVEROUTING.md

1: # AI-kompetencer og dynamisk opgaverouting
5: ## 1. Anbefaling
7: Brug først eksisterende abonnementer og én primær udfører pr. opgave. Tilføj uafhængigt review, når risikoen kræver det. Vælg efter dokumenteret kvalitet på vores opgavetype, nødvendige værktøjer og samlet omkostning ved en accepteret leverance. Afprøv API-routing særskilt, hvis målingerne viser en besparelse efter drift og integrationsarbejde.
11: ## 2. Foreløbig kompetenceafklaring
15: | Deltager | Foreslået startrolle | Grundlag og vigtig begrænsning |
18: | ChatGPT | Kravafklaring, produktdiskussion, forklaring og anden gennemgang af en beslutning | Skal have relevante kilder og konkret værktøjsadgang. Kan dele modelfamilie med Codex; ikke automatisk uafhængig reviewer. [Modeller](https://learn.chatgpt.com/docs/models) |
20: | Kimi | Afgrænset implementering, branchanalyse og evidenskontrol | Projektets review og korrigerede branchmåling giver konkret erfaring, inklusive behovet for populationskontrol. Versionsvalg skal registreres. [Modelopslag](https://platform.kimi.ai/docs/api/list-models) |
21: | Z.ai | Pilot på afgrænsede kodeændringer, tests og struktureret review | Fast projektdeltager; ingen sammenlignelig lokal måling er etableret i denne pakke. GLM-version og agentmiljø skal afklares. [Oversigt](https://docs.z.ai/guides/overview/overview) |
24: | Grok | Pilot på kildebaseret research og kritiske modargumenter | Søgning, kildekvalitet og adgang skal verificeres for den konkrete model og klient. [Modeller](https://docs.x.ai/developers/models) |
29: ## 3. Kompetencekort — udfyld pr. konfiguration
31: Et kort identificerer produkt, leverandør, model/version (eller ukendt), indsatsniveau, klient, værktøjer, adgangsgrænser, dato og evidenscommit. Registrér følgende som **ikke målt**, **bestået med evidens**, eller **utilstrækkeligt til denne opgaveklasse**:
33: - Forstår krav og finder eksisterende løsninger før ny implementering.
42: Mål første-gangs-accept, fejl efter review, kritiske oversete fejl, genarbejde, gennemløbstid, forbrug og menneskelig kontroltid. En samlet pointscore må ikke skjule et svigt i sikkerhed eller mandat.
46: ## 4. Routingbeslutningen
55: Budgetrammen skal angive abonnementer, ekstra API-loft, loft pr. opgave og et samlet håndhævet loft ved parallelle opgaver. Ukendt budget giver ikke lov til nyt forbrug. En routers prispræference er ikke et økonomisk stop. Ved utilstrækkeligt budget returneres en konkret begrænsning; kvalitets- eller sikkerhedskrav sænkes ikke tavst.
57: ## 5. Eksisterende routingmuligheder
61: | [OpenRouter Auto Router](https://openrouter.ai/docs/guides/routing/routers/auto-router) | Automatisk valg mellem tilladte API-modeller, med model- og prispræferencer | Ekstra databehandler/gateway og API-forbrug; cost tier er ikke et hårdt budgetloft. Kræver vores evaluering. |
62: | [LiteLLM Router](https://docs.litellm.ai/docs/routing) | Fordeling mellem modeldeployments efter bl.a. belastning, latency og pris | Ikke i sig selv bevisbaseret valg af bedste projektagent; kræver policy, måling og drift. |
64: | [Copilot Auto](https://docs.github.com/en/copilot/concepts/models/auto-model-selection) | Automatisk modelvalg inden for Copilots understøttede produkter og abonnement | Fordeler ikke arbejde til alle vores separate AI-apps. Faktisk modelvalg skal kunne spores. |
66: **Anbefalet rækkefølge:** manuel, dokumenteret opgavefordeling → lille kontrolleret måling → eventuel API-router. En modelrouter vælger en model til et kald; en projektkoordinator håndterer opgaver, værktøjer, ejerskab, review og recovery. De er forskellige funktioner. Ingen af disse løsninger er installeret eller tilkoblet Headend her.
68: ## 6. Mission Framework og Mission Platform
70: Framework har allerede principper, vi bør genbruge:
72: - [Trust bootstrap og evidence maturity](https://github.com/froekjaer/mission-framework/blob/a6234ba4232a4e337843189fe6f9b4f497bb1527/docs/operational/TRUST-BOOTSTRAP-CREDIBILITY-ONBOARDING-EVIDENCE-MATURITY.md): tillid opbygges gennem evidens. En foreslået rolle er ikke en reproduceret kompetence.
73: - [Uafhængig verifikation](https://github.com/froekjaer/mission-framework/blob/a6234ba4232a4e337843189fe6f9b4f497bb1527/docs/ENGINEERING_CONTINUITY_AND_INDEPENDENT_VERIFICATION.md): kontinuitet og kontrol skal overleve den enkelte session.
76: **Forslag til Framework-feedback:** eksplicit princip om evidensbaseret, genvurderbar kompetence og budget under ufravigelige mandat-/datagrænser. Før et nyt Framework Finding oprettes, skal eksisterende findings kontrolleres for overlap. Der er ikke oprettet et nyt kanonisk ID her.
80: ## 7. Næste afklaring og ansvar
82: Codex har udarbejdet forslaget efter Peters instruktion. Peter afklarer eksisterende abonnementer og ekstra forbrugsramme; derefter kan en konkret lille pilot prissættes og fordeles. Review af denne udvidelse udestår. Aktive leverancer føres i det eksisterende pakkesporregister, ikke i en ny konkurrerende backlog. Ingen automatisk genmåling eller scheduler er oprettet.
84: ## 8. Konkret integrationsforslag — Collaborative Intelligence
86: **Status:** foreslået placering, ikke vedtaget upstream. Peter har autoriseret udarbejdelsen. Kildebaseline: Collaborative Intelligence `278d8698373e46a28191c065e223dc5c0d98d5b3`, Mission Framework `a6234ba4232a4e337843189fe6f9b4f497bb1527`, Mission Platform `782ef287ef3ae4767503a50c1085f823ec4707d4`.
90: ### Foreslået indhold pr. repository
100: ### Mindste afprøvning og beslutningsgrundlag
106: Platform-piloten skal kunne demonstrere: fravalgt provider bruges aldrig; data sendes kun til tilladte forbindelser; opbrugt gratis kvote giver vent/stop uden betalt fallback; modelsvigt har begrænset retry; reviewer kan identificere input og faktisk udfører; parallelle opgaver kan ikke overskride et fælles loft. Brug simulerede forbindelser til disse kontroltests før eventuelle eksterne kald.
108: ### Budget og gratis ressourcer — Peters oplysninger
110: Rapporteret abonnement: Codex/ChatGPT $20, Claude $17, Kimi $19 og Z.ai $16 pr. måned; samlet $72/måned ($864/år ved uændrede priser). Dette er brugeroplyst udgift, ikke verificerede fakturaer eller godkendt forbrugsloft. Peter ønsker gratis ressourcer og routing undersøgt; der er ikke godkendt ekstra betaling.
112: Kandidater: [OpenRouter Free Router](https://openrouter.ai/docs/faq) og [Groq Free Plan](https://console.groq.com/docs/rate-limits). Brug kun godkendte modeller/providers og registrér faktisk valg. OpenRouter `openrouter/free` adskilles fra betalt Auto-routing. [Z.ai Coding Plan](https://docs.z.ai/guides/overview/quick-start) har særskilt endpoint til understøttede værktøjer; det er ikke dokumentation for ret til vilkårlig generel API-routing. Kontoadgang, datavilkår og kvoter verificeres før aktivering. Ingen API-nøgler skal placeres i Git, handover eller reviewmateriale.
114: ### Leverancer og status
116: Dette afsnit er integrationsoplægget til samlet review. Næste leverance er afgrænsede upstream-forslag efter kontrol af hvert repositories aktive arbejde og bidragsregler. Codex er udfører på dette oplæg; ingen andre sessioner er automatisk tildelt arbejde. Upstream-filer er endnu ikke ændret, og ingen pilot er kørt. Afgrænsning og review skal bevare CI's eksisterende forskningsposture og Frameworks semantiske ejerskab.
118: ### Prioriteringsbeslutning — Peter, 2026-09-13
120: Solar Eclipse sættes på sidelinjen indtil en senere eksplicit genoptagelse. Den er ikke en forudsætning for routingafprøvning eller Mission-Platform-arbejde. Dette afløser tidligere forslag i dette oplæg om at bevare den som aktiv gate. Historisk rolle slettes ikke. Upstream AI_CONTEXT/README skal ved næste afgrænsede ændring afspejle beslutningen; de er endnu ikke opdateret. TimeLapse Pro er den planlagte aktuelle engineering-case, ikke omskrevet til historisk første referenceimplementering.

## Dokumentation/Arkitektur/CORE_DESIGN_PRINCIPLES_ANALYSE_2026-09-13_CLAUDE.md

1: # Semantisk analyse — `agent/core-design-principles` mod aktuel main
10: ## Sammenfatning
14: **Vigtigste enkeltfund:** Del I's centrale, mest konsekvensfulde princip (Princip 2/3 — "projektdata slettes aldrig automatisk") er **allerede implementeret på main**, og har været det **siden før dokumentet blev skrevet** (commit `15038101`, 2026-07-15 — to uger før dokumentets dato). Dokumentets egen "åbne afklaringer"-tabel beskriver dette forkert som en åben konflikt mod "eksisterende automatisk cleanup" — den beskrivelse er nu selv forældet.
16: ## Klassifikation
18: ### A) Allerede dækket på main
20: - **Princip 2 (Projektdata slettes aldrig automatisk) og Princip 3 (Retain until explicit disposition):** `headend/main.py::_run_retention_cleanup()` er allerede en no-op der eksplicit logger *"Capture deletion is prohibited"* og altid returnerer `deleted_count: 0` — implementeret **2026-07-15** (`fix(storage): enforce immutable capture retention on headend`), to uger *før* dette dokument. Sletning sker kun via `headend/services/capture_deletion_service.py::delete_capture()`, som kræver eksplicit `deletion_reason` (whitelist: defective/unwanted/gdpr_request/other), `performed_by`, og skriver en uafhængig `CaptureDeletionLog`-audit-post. Dette er funktionelt identisk med principperne, allerede håndhævet i kode — ikke kun i hensigt.
21: - **Princip 16 (Platform/payload adskilt):** Dokumentet selv erklærer sig konsistent med ADR-001 (Accepted). Ingen konflikt, ingen ny beslutning nødvendig.
22: - **Princip 8 (integritet/checksums), delvist:** Signerede update-artifacts, SHA-256-baseret release-kvittering (`release_receipt_matches_artifact`) og backup-integritetsverifikation (`backup_integrity.validate_plain_pg_dump`) findes allerede i separate, modne undersystemer — spredt, men reelt implementeret, ikke kun princip.
23: - **Princip 12 (least privilege / explicit authority), delvist:** RBAC-roller (admin/operator/viewer m.fl.), `require_role()`-guards og tidsbegrænsede provisioning-tokens findes allerede.
25: ### B) Stadig relevant og unikt (ikke bygget, intet der modsiger det)
27: - **Princip 4-6 (eksplicit projekt-lifecycle med tilstande `planned→...→deleted`, styret "Afslut projekt"-flow):** Verificeret at der **ikke** findes en `Project`-model i `headend/database.py` — den eksisterende model er stadig Customer → Site → Camera/Device, præcis som dokumentets egen "as-is"-tabel siger. Dette er reelt, ikke-bygget arbejde.
28: - **Princip 9-11, 21-25 (evidens/fortolkning-adskillelse, fail-safe, sikkerhed integreret, standarder risikobaseret, observability, alarm-lifecycle):** Generiske, velargumenterede principper uden et enkelt canonisk referencepunkt i repoet i dag — spredt praksis, men ikke samlet som håndhævet politik nogen steder.
29: - **De 6 kandidat-ADR'er i §49** (Local Service Gateway, Physical Presence Requirement, Bluetooth as Bootstrap Transport, Capability-based Service Authorization, No General-purpose Shell, Retain until Explicit Disposition): Ingen af dem er blevet til en faktisk ADR. Kun `ADR-001` og `ADR-003` findes i `Dokumentation/ADR/`.
31: ### C) Superseded/forældet
33: - **Dokumentets egne pointer-ændringer i `00_START_HER.md`, `ADR/README.md`:** Disse blev skrevet mod en main fra 2026-07-31 og beskriver nu forkert nutid — fx "Headend (R&D)" (main siger nu "Headend (prod)"), forældede storage-stier, en `ADR/README.md` uden ADR-003. En direkte re-applicering af branchens patch ville **reintroducere forældede driftsfakta**. Hvis dokumentet skal linkes fra disse filer, skal det gøres som en frisk tilføjelse mod nutidig main, ikke en genanvendt patch.
36: ### D) Konflikt med senere accepteret/implementeret arbejde — **kræver Peters beslutning**
39:   **Dette er ikke en ren "allerede dækket"-situation** — det er en reel arkitektonisk divergens: en simplere løsning er allerede bygget og i brug, mens dokumentet beskriver en langt mere elaboreret målarkitektur. Peter skal beslutte: (a) lad den simple løsning stå og arkivér Del II's mere elaborerede model som fremtidig, ikke-prioriteret retning; (b) brug dokumentet som roadmap til at udvide den eksisterende løsning gradvist; eller (c) formelt supersede Del II med en ny, kort ADR der beskriver den valgte, simplere retning som den faktiske beslutning.
40: - **Sideobservation, ikke i Del II, men direkte relevant:** Under denne batch fandt jeg en ubeslægtet, men beslægtet sag — en ældre, aldrig merget branch (`codex/edge-terminal-renderer`) forbedrer et **allerede eksisterende** generelt shell-endpoint (`/mgmt/cli/bash/*` i `edge/scripts/totp-service.py`, WebSocket-baseret på main i dag). Dokumentets egen Princip ("No General-purpose Shell", §49) og §43 ("Et POST /run-command-endpoint findes ikke i almindelig service-mode") **er i direkte modstrid med denne allerede-eksisterende, main-side funktionalitet** — main har allerede et generelt bash-shell-endpoint tilgængeligt via den lokale TOTP-gate. Se separat R04-batch-rapport for detaljer; nævnes her fordi det er direkte relevant for om Princip/ADR-kandidaten "No General-purpose Shell" overhovedet er en gyldig fremadrettet retning, eller om den kræver en bevidst undtagelse/retrofit-beslutning for det der allerede kører.
42: ### E) Uklart / kræver Peters beslutning (ud over C/D)
44: - Hvorvidt de 6 kandidat-ADR'er skal tages op til formel beslutning nu, samlet eller enkeltvis, eller forblive et referencedokument.
45: - Om selve dokumentet (Proposed, 585 linjer, aldrig merget) skal: (a) merges som *Proposed*-referencemateriale (uden at hævde nogen del er Accepted), (b) forkortes til kun de dele der er verificeret stadig relevante (B), eller (c) arkiveres med en kort begrundelse og henvisning til hvor dets reelt værdifulde dele (projekt-lifecycle-modellen) i stedet fanges (fx som et fremtidigt kravregister-punkt).
47: ## Stop-gate — eskaleres til Peter

## Dokumentation/Arkitektur/Headend_Main_Modularisering_Status_2026-08-26.md

1: # Headend `main.py` — Modulariserings-status
9: ## Hvorfor
18: akkumuleret **to konkurrerende, ad-hoc måder** at omgå den samme cirkulære
24: ## Tal — før og efter
35: ## Den arkitektoniske kerne-fix: `headend/auth.py`
68: ## Nye/udvidede moduler denne nat
82: ## Etablerede mønstre (til fremtidige udtrækninger)
109: ## Hvad står stadig i `main.py` — grov oversigt
116: | **Updates/artifacts/releases** | 26 | Størst. Egne baggrundstråde (git-tag poller, os-bundle poller, headend-self-update). Planlagt SIDST, splittet i 2 PR'er — det er selve headendens self-update-maskine. |
120: | **OpenWebUI-integration** | 10 | Selvstændig, egen baggrundstråd. God kandidat. |
130: | **Change tickets** | 4 | Refererer Pending Updates — bør flyttes SAMMEN med Updates-domænet, ikke isoleret. |
136: ## Vigtige opdagelser undervejs (ændrer den oprindelige plans rækkefølge)
160: ## Verifikation — hvordan hver ændring blev bekræftet
172: ## Næste skridt

## Dokumentation/Arkitektur/Modularisering_Platform_Payload_Plan.md

1: # Fra TimeLapse Pro til modulær edge-platform — plan & GitHub-strategi
8: ## 1. Målet i én sætning
16: ## 2. Hvad er kerne (genbruges) vs. payload (udskiftes)
24: | Remote access (tunnel + JIT/AccessTicket + session recording) | Domæne-UI-flader (i dag billed-galleri, tag-søgning) |
33: ## 3. Kontrakten mellem kerne og payload (Codex' skærpelse indarbejdet)
35: Et simpelt interface er ikke nok. `PayloadDriver` skal ledsages af et **capability manifest**, så platformen kan køre en ukendt payload sikkert:
57: ## 4. Repo-strategi: hvordan de to spor lever side om side
64: **B) Platform som versioneret pakke, payloads som separate repos (mål på sigt)**
73: ## 5. Faseinddelt roadmap (additivt — bryder intet undervejs)
75: **Fase 0 — Beslut & indram (ingen kode).** ADR-001 vedtager platform/payload-snittet, kontrakten og repo-modellen (A). Beslut navngivning: nye platform-tabeller/API bruger neutrale ord ("asset"/"node"), men **eksisterende camera/capture-kontrakter omdøbes IKKE** (additiv-princippet, Codex enig).
89: ## 6. Kan GitHub hjælpe? Ja — konkret mapping
95: | **Parallelt ejerskab** (kerne-team vs. payload-team, menneske+AI) | `CODEOWNERS` pr. sti → automatiske review-krav; separate PR-godkendere for `platform/` vs. `payloads/` |
100: | **Miljøer (rd/staging/prod) + agent-lockout** | **GitHub Environments** med protection rules + required reviewers → maps til jeres 3-maskiners topologi; hemmeligheder pr. miljø; prod bag manuel godkendelse |
102: | **CRA/sikkerheds-posture pr. modul** | **Dependabot** (afhængigheder), **CodeQL** (SAST), **SBOM-eksport** (Actions), branch protection + required checks (jeres unit-gate + arch-ratchet) |
113: ## 7. Risici & vagtskel (så modularisering ikke bliver et sidespor)
118: - **Sikkerhed følger med, ikke bagefter.** Capability manifest = least privilege fra dag 1; remote access til nye OT-verticals SKAL gå gennem platformens JIT-model (R19/break-glass), aldrig direkte portåbning.
122: ## 8. Anbefalede næste 3 handlinger

## Dokumentation/Arkitektur/TimeLapse_Arkitektur_og_Dataflow.mermaid.md

1: # TimeLapse Pro — Arkitektur & Dataflow (Mermaid)
4: Diagrammerne beskriver (1) systemkontekst, (2) dataflow/komponenter, (3) IEC 62443-zoner & miljøer, (4) capture→tag-sekvens og (5) målbilledet: modulær platform/payload. Ret dem sammen med koden — de er versionsstyrede.
10: ## 1. Systemkontekst (hvem/hvad taler med systemet)
44: ## 2. Dataflow & komponenter (det centrale diagram)
114: ## 3. IEC 62443-zoner & miljøer (deployment)
170: ## 4. Sekvens: capture → upload → AI-tag → UI
199: ## 5. Målbillede: modulær platform + udskiftelig payload

## Dokumentation/Assessment_2026-07_3P_RECONCILIATION_2026-08-25.md

1: # Reconciliation — 3P Assessment 2026-07
8: ## Formål
14: ## Executive Status
26: ## Statusmatrix
30: | TPA-00 / SEC-016 factory BT-TOTP fallback | Kritisk, fail-open known default credential | **LUKKET som delt fallback.** `SEC-016_Factory_BT_TOTP_Bootstrap_Gap.md` dokumenterer closure; tests forbyder `JBSWY3DPEHPK3PXP` i kørende kode. Per-device/auto-sync/bootstrap-sporet er efterfølgende bygget og dokumenteret. | Ingen ny P0 fra 3P. Hold regressionstests og lifecycle-inventory for offline recovery. |
31: | TPA-01 route-auth canary | Først høj, derefter nedgraderet til lav efter Codex CI-evidens | **ERSTATTET/LUKKET SOM BLOCKER.** Branch protection og route-auth/gov-gates har siden været del af normal CI/PR-flow. | Bevar route-auth ratchet. Ingen selvstændig 3P-action. |
32: | TPA-02 Edge-signering med Bearer-token/HMAC, mTLS/enheds-CA mangler | Mellem, før ny Edge | **ERSTATTET AF WP-1/WP-4.** Edge credential inventory, bootstrap lifecycle, Edge-owned SSH/TLS key generation, signed provisioning envelope og CSR path er nu implementeret som target-model. Legacy adapters findes stadig for eksisterende Edges. | Følg WP-4 remaining legacy path-dokumentation; ingen tilbage til 2026-07 design. |
35: | TPA-05 cookie/JWT skærpelser | Lav | **STADIG RELEVANT SOM HYGIENE.** Ingen evidence for akut regression; bør ligge som normal security hardening. | P3/P2 afhængigt af Internet exposure: SameSite/CSRF review for muterende endpoints. |
36: | TPA-06 replay-vindue for signed Edge requests | Lav/usikkerhed | **DELVIST ERSTATTET.** Trust Service/EdgeServiceGrant har replay/challenge-tests; Edge API request replay bør fortsat have eksplicit test hvis ikke allerede dækket. | P2/P3 test gap: dokumentér/tilføj nonce/skew test for Edge request signing. |
38: | TPA-10 monolit `headend/main.py` | Høj teknisk gæld | **STADIG RELEVANT, men styret.** Arkitektur-ratchet og router-udtræk er aktiv praksis; Codex-Audit gentager monolitten som P2, ikke release-blocker. | Fortsæt ratchet og små router/service udtræk. Ingen big-bang. |
40: | TPA-12 tråd-pr.-hændelse uden begrænsning | Mellem | **UKLAR / KRÆVER NY MÅLING.** Ikke valideret i denne reconciliation; nyere architecture work kan have ændret hot paths. | Re-test under load/soak før production scale claim. |
41: | TPA-13 module-level caches | Lav | **STADIG HYGIENE.** Ikke en blocker. | Tag opportunistisk sammen med settings/cache work. |
45: | TPA-20..24 UI/UX navigation/sprog/persona | Mellem/lav | **DELVIST LUKKET/OVERHALET.** Hjælpemenu, CMDB-version UI, update-indikatorer og technician UI er ændret siden. | Kræver ny UI-review mod current UI; ikke brug 31. juli-listen direkte. |
46: | GDPR compliance gaps | Delvist, DPA/roles/retention supervision mangler | **STADIG RELEVANT, men status ændret.** Edge-local retention og Headend retention/audit er stærkere; DPIA/DPA/controller-processor/site signage og TV-overvågning er stadig business/legal readiness. | Brug `Codex-Audit/06_COMPLIANCE_ASSESSMENTS.md` som aktuel kilde; lav kunde/site compliance pack før kommerciel produktion. |
47: | CRA readiness | Blocker pga. TPA-00, SBOM/update gaps | **STADIG RELEVANT, MEN IKKE SAMME BLOCKER.** Factory TOTP er lukket; artifact signing, SBOM/update governance og WP-4 er stærkere. Formal product classification/support period/VEX/CE file mangler stadig. | Brug Codex-Audit CRA-afsnit og release evidence pack. |
48: | IEC 62443 | Delvist, TPA-00 + mTLS/enheds-CA gaps | **DELVIST ERSTATTET.** Trust Service, PDP, EdgeServiceGrant, WP-4 provisioning og technician platform har ændret risikobilledet. | Ny 62443 mapping skal baseres på current architecture, ikke 31. juli. |
49: | ISO 27001 / R09 restore evidence | Restore-test go-live blocker | **STADIG RELEVANT.** Backup er forbedret og restore-verifiable mekanik findes, men egentlig restore rehearsal/evidence er stadig et stærkt acceptance gate før brede compliance claims. | Planlæg og dokumentér Headend DB + capture-store restore rehearsal. |
50: | AI Act / AI register | Delvist | **STADIG RELEVANT.** AI-funktioner er fortsat støtte/diagnostik, men register/rolleklassifikation/human oversight bør være levende dokumentation. | Indgår i compliance pack. |
51: | GEN-01 SFTP ingress i generator | Høj før staging | **DELVIST ERSTATTET AF SENERE SITE-SFTP/RBAC-ARBEJDE.** Site SFTP er nu behandlet som site/RBAC-owned credential/profile, og Edge-consumed SFTP er inventory-aware. Generatorens fulde fresh install path bør dog vurderes mod current architecture. | Re-test headend/site provisioning from blank install; ikke merge gammel generator-plan blindt. |
53: | GEN-03/04/11 tunnel-port/prod image build beslutninger | Peter-beslutninger | **ERSTATTET AF LOCKED ARCHITECTURE + WP-4.** Generic signed image + provisioning envelope er target; reverse tunnel work er efterfølgende behandlet i Trust/SSH tunnel UX. | Brug locked decisions og WP-4 docs. |
54: | E-01/E-02 per-device identity/fail-closed enrollment | Kritisk | **LUKKET/ERSTATTET AF WP-4 BASELINE.** Signed provisioning envelope, one-time bootstrap consume, hardware binding, Edge-owned keys og lifecycle inventory er implementeret/testet. | Følg WP-4 exit/remaining legacy paths. |
55: | Framework v1 contracts path | Additivt næste skridt | **STADIG STRATEGISK RELEVANT, MEN IKKE RELEASE-BLOCKER.** Mission Framework alignment er nu behandlet i Codex-Audit og OP-001 loader. | Hold som later architecture governance track. |
57: ## Fund der stadig bør oprettes eller bevares som aktive work items
66: ## Fund der ikke bør genåbnes fra 3P-pakken
69: - Route-auth canary som høj blocker: nedgraderet og overhalet af CI-evidens.
71: - Gammel retention supervision som “stille manglende sletning”: Edge-local uploaded FIFO retention er implementeret og verificeret live; eventuel opfølgning skal handle om current retention telemetry, ikke den gamle no-op tilstand.
74: ## Beslutning

## Dokumentation/BACKUP_RESTORE_TEST_PROCEDURE_v1.md

1: # Backup/restore-test procedure (v1)
8: ## Hvorfor dette dokument
16: ## Forudsætninger
27: ## Trin 1 — Pak arkivet ud til et scratch-område
37: config-filer), `SYSTEMINFO.txt`. Bekræft filstørrelser er fornuftige (SQL-filen bør være
40: ## Trin 2 — Gendan databasen til en SCRATCH-database (ikke produktion)
55: Sammenlign tallene med produktionsdatabasen (kør samme queries mod `timelapse_db`) — de bør
62: ## Trin 3 — Verificér config-delen
69: hvis en fil mangler i listen, betyder det den ikke fandtes på disken ved backup-tidspunktet
72: ## Trin 4 — Verificér billed-mirroren (den nye del fra i nat)
88: De to tal bør være tæt på ens (mirroren er inkrementel — første kørsel kan tage lang tid og
98: ## Trin 5 — Dokumentér resultatet
104: ### Restore-test udført <dato> af <navn>
114: ## Hvad denne test IKKE dækker (vær ærlig om det i go-live-vurderingen)
126:   bør indgå eksplicit i RTO/RPO-dokumentationen (E-07).
128: ## Hvorfor jeg ikke selv har kørt dette i nat

## Dokumentation/BLE_TECHNICIAN_ACCESS_2026-09.md

1: # BLE Technician Access — implementation baseline
3: ## Purpose
9: ## Verified current state
19: ## Target
31: The adapter must create an explicit offline-recovery ServiceSession after a
33: must never call GPIO, gphoto, ModemManager or systemctl directly.
35: ## Security rules
48: ## Client boundary
50: The iPhone UI must be a native CoreBluetooth client (optionally distributed via
52: but must call the BLE service rather than duplicate hardware behavior. Building
56: ## Current implementation

