# Raw archaeology extract — current 006

## Dokumentation/Codex-Audit/08_EVIDENCE_LOG.md

1: # Evidence Log
3: ## Repository state
12: ## Operational documents read
23: ## Mission Framework files read
30: ## Code areas inspected
50: ## Open PR evidence
58: - #81 `docs: Kimi review — GRC decision-pending list + documentation gap analysis (2026-08-19)`
60: ## GRC evidence limitation
69: The assessment therefore uses earlier verified GRC observations from this review thread as secondary operational evidence. This limitation should itself be fixed because OP-001 depends on reliable access to existing findings/actions.
71: ## Official regulatory/standards sources checked
84: ## Verification run
108: ## Not performed

## Dokumentation/Codex_Dokumentationsstyring_Review_2026-07-02.md

1: # Codex review — dokumentationsstyring og v11-strategi
7: ## Kort konklusion
9: Jeg er enig i målet, men ikke i en blind "alt til v11 nu"-runde.
12: autoritative `*_v10.md` dokumenter og `Gamle versioner/` som arkiv. Det næste skridt bør være en
21: ## Autoritative dokumenter lige nu
45: ## Fund ved hurtig review
47: ### 1. `00_START_HER.md` er den rigtige session-anchor
49: Nye Claude/Codex-sessioner bør starte her. Den indeholder allerede:
57: Min anbefaling er at holde den kort og skarp. Den skal ikke blive endnu en fuld dokumentation.
59: ### 2. Broken/forældet reference
67: ### 3. RPi5-forstyrrelsen er allerede markeret, men ikke helt fjernet
77: Det er godt for historik, men dårligt som session-reference. I v11 bør de enten:
82: ### 4. Kamera-understøttelse bør beskrives som en matrix
84: Fremadrettet dokumentation bør ikke sige "Nikon Z30 erstatter Canon" for hårdt.
86: Den bør sige:
90: | Nikon Z30 | Aktiv/lab-primary | Fokus, live view, eksponering og Z30-profil skal fortsat hærdes |
91: | Canon EOS 1000D | Skal understøttes | gphoto2/relay-baseret legacy/field support |
92: | Canon EOS 1300D | Skal understøttes | tidligere lab- og edge-erfaring findes |
93: | Canon EOS 2000D | Skal understøttes | forventet Canon EOS/gphoto2-variant, kræver profiltest |
95: Kamera-specifikke forskelle bør ligge i en dedikeret konfig-/driverprofil, ikke spredt gennem
98: ### 5. "Seneste version af alle dokumenter som .md" er rigtigt, men bør være manifest-styret
121: ## Min anbefalede v11-rækkefølge
134:    Skal valideres mod launchd, nginx, PostgreSQL, storage paths og nuværende services.
137:    Skal opdateres med Edge QA/NPU, real-world-only billedtræning, RBAC/SFTP/API status og de
144: ## Hvad Claude gerne må gøre
146: Claude må gerne konsolidere tekst og lave v11-drafts, men bør markere alle kode-/driftsudsagn med:
157: ## Hvad jeg ikke anbefaler
161: - At slette RPi5/Canon-historik helt. Den skal arkiveres og tydeligt markeres som historisk, ikke
164:   men driftsnære sandheder skal leve i de specialiserede dokumenter.
166: ## Codex' sidste ord

## Dokumentation/Codex_Edge_AI_NPU_Modes_2026-06-28.md

1: # TimeLapse Pro - Edge AI/NPU modes
5: ## Formål
7: Edge AI skal forbedre billedkvalitet lokalt på Orange Pi 4 Pro/A733-lignende hardware:
16: Semantisk tagging af byggepladsindhold bør fortsat ligge i headend/cloud-flow med review. Edge AI er deterministisk QA og kamera-feedback.
18: ## Modes
31: `quality.adaptive_exposure.enabled` skal stadig være `true`, før Edge faktisk justerer EV mellem captures.
33: ## NPU-kontrakt
48: Runneren skal skrive præcis ét JSON-objekt til stdout. Minimum:
61: Den nuværende runner er NPU-klar, men falder tilbage til CPU/OpenCV hvis vendor runtime/model mangler. Den returnerer runtime-detektion, så hardwarestatus kan ses i QA-resultatet.
70: ## QA modelkontrakt
111: ## Orange Pi 4 Pro/A733 manualnoter
145: - `missing=["viplite_runtime_or_device"]`: VIPLite runtime/device driver mangler eller er ikke synlig.
146: - `missing=["model_path"]`: `.nb` modellen mangler på den konfigurerede sti.
148: Første produktionsmodel bør sandsynligvis være en lille klassifikationsmodel, ikke en stor vision-LLM. Den bør trænes på ovenstående kontrakt og eksporteres via Allwinner ACUITY til `.nb`.
150: ## Testbilleder
190: `--input-layout nchw_bgr` er kun til SDK ResNet-demoen. Den rigtige TimeLapse QA-model bør følge
210: ## Morgenens hardware-test
220: ## Orange Pi 4 Pro teststatus 2026-06-28
244: ## Næste modelmilepæl
255:   ingen sikre `ok`-billeder. Næste datasætrunde skal derfor mine `ok` målrettet i dagslys.
300: Praktisk krav før produktionsdrift: valider modellen på mindst `test`-split og en frisk dag fra
301: hver kameratype. CPU/OpenCV optimizer skal forblive fallback, indtil NPU-modellen er bedre end
304: ## Edge QA model-v1 status 2026-06-30
344: men den er ikke produktionsklar til autonom drift. Drift skal fortsat bruge CPU/OpenCV optimizer som
349: ## Edge QA MobileNet smoke 2026-06-30
377: til `.nb`, men denne MobileNet-ONNX skal stadig igennem Allwinner ACUITY-konvertering. Docker daemon
380: Driftsbeslutning: MobileNet-smoke er brugbar til integrationstest og som assist-signal. Den bør ikke
385: ## NPU-afklaring 2026-06-30
387: Ja: den endelige edge-model skal køre på NPU'en. Orange Pi/Allwinner-kæden accepterer dog ikke ONNX
388: direkte; modellen skal konverteres til `.nb` via ACUITY/pegasus og køres af VIPLite-wrapperen.
398: - Import-test stopper på `Need to set environment variable ACUITY_PATH`, hvilket betyder at selve
419: ## NPU-runtime status 2026-07-02
436: Driftsstatus: `assist`, ikke autonomt. Runtime virker, men den kvantiserede `.nb` skal kalibreres
437: bedre, fordi scorefordelingen endnu ikke matcher ONNX CPU-baseline tæt nok. Næste runde bør være en

## Dokumentation/Codex_Kode_Drift_Validering_for_v11_2026-07-02.md

1: # Codex kode-/driftsvalidering for v11
7: ## Konklusion
15: - eller markeres tydeligt som historik/planlagt arbejde.
19: ## Valideret driftstilstand
47: ## Valideret database/status
86: ## Kodevalidering
94: - Canon EOS 1000D og Nikon Z30 mangler eksplicit shutter-rating i diagnostics og falder derfor tilbage på default.
99: - Det skal gøres dynamisk før dokumentationen siger, at UI fuldt understøtter Canon 1000/1300/2000 og Nikon Z30 side om side.
107: - Derfor skal v11 beskrive RBAC som API-/join-baseret tenant scoping, ikke som en fysisk sikkerhedsgaranti alene på `captures.customer_id`.
113: - Dette matcher NAS/mapped-drive-strategien, men v11 bør kræve en dokumenteret mount-switch-test før prod.
119: - Den større real-world QA-model er ikke klar til drift: real-world-only træning blev stoppet pga. ustabilitet, og tidligere holdout-model viste domain gap på Travbyen.
122: ## V11-blokkere eller kræver tydelig markering
130:    - Security/Compliance/RBAC-dokumenter bør markere MFA som restpunkt eller aktiveres før v11-go-live.
134:    - Dokumenter skal skelne mellem edge-service, Mac/headend node-agent og eventuel Orange Pi node-agent.
137:    - `TL-C87FF9587CA0` er online, men mangler `hardware_model` og `camera_model` i `devices`.
138:    - CMDB/System Inventory bør ikke påstå fuld hardware-inventory-kvalitet, før collector/backfill opdaterer dette.
145:    - Canon EOS 1000D og Nikon Z30 mangler eksplicit shutter-rating/diagnostic modeldata.
146:    - Kan være acceptabelt med default, men dokumentationen skal kalde det "generic fallback" hvis ikke rettet.
157:    - RBAC/scoping er til stede i kode, men der mangler en eksplicit endpoint-by-endpoint integrationstest, der beviser at kunde A ikke kan læse kunde B billeder/API-data.
159: ## Dokumentkonsekvens
161: Disse dokumenter bør først have v11 efter målrettet opdatering:
183: - Dokumenter mapped/NAS-drive-dynamik som DB-konfigureret storage-root og SFTP-root, med krav om mount-switch-test.
185: ## Anbefalet næste rækkefølge
196: ## Godkendelsesregel for v11

## Dokumentation/Codex_Kodereview_2026-08/CODE_REVIEW_2026-08-03.md

1: # TimeLapse Pro - kodegennemgang 2026-08-03
3: ## Konklusion
10: Det er dog **ikke klar til en ny produktionsgodkendelse**. Tre P0-fund skal
15: ## Fund
17: ### P0-01 - fælles BT-PAN TOTP-fabrikshemmelighed
29: hemmelighed ved kamera-/Edge-provisionering. Ikke-provisioneret Edge skal
35: ### P0-02 - OS-bundlebuilder har ukontrolleret input i Docker-kørsel
54: ### P0-03 - integrationstest kan ramme aktiv Headend
65: Gør `TIMELAPSE_TEST_BASE_URL` obligatorisk for `-m integration`, og afvis
71: ### P1-01 - rollback er uatomisk
81: ### P1-02 - backup er delvist forældet
91: ### P1-03 - artifact-signering falder tilbage til hashbinding
94: `system-hash`, hvis GPG mangler eller fejler.
99: ### P1-04 - frontend-afhængigheder har kendte advisories
108: ### P1-05 - kodekvalitetsgates er ikke effektive nok
116: ### P2-01 - aktiv dokumentation og deploymentstier er ikke synkroniseret
126: ## Positiv evidens

## Dokumentation/Codex_Kodereview_2026-08/README.md

1: # Codex kodegennemgang - august 2026
9: ## Indhold
16: ## Afgrænsning

## Dokumentation/Codex_Kodereview_2026-08/REMEDIATION_PLAN_2026-08-03.md

1: # Afhjælpningsplan 2026-08-03
3: ## P0 - før produktionsaccept
11: ## P1 - næste releasecyklus
18: 5. Indfør ruff-/ESLint-ratchet for ændret kode og reducer backlog modulvis.
20: ## P2 - løbende kvalitet
27: ## Releasegate

## Dokumentation/Codex_Kodereview_2026-08/TEST_EVIDENCE_2026-08-03.md

1: # Testevidens 2026-08-03
3: ## Udførte tests
13: | Ruff statisk analyse | FAIL/backlog | 2.103 fund. |
14: | ESLint gate | FAIL/backlog | 165 errors og 20 warnings. |
16: ## Integrationstests - bevidst ikke kørt
31: ## UI-teststatus
38: ## Kendte buildadvarsler

