# Raw archaeology extract — current 007

## Dokumentation/Codex_Kodereview_2026-08/UI_TOOLTIP_AUDIT_2026-08-03.md

1: # UI- og hjælpetekstaudit 2026-08-03
3: ## Princip
5: Alle navigationspunkter, ikonknapper og konfigurationsfelter skal have en
8: felter skal have et synligt `HelpCircle`-ikon med samme indhold.
10: ## Fælles navigation
18: ## Prioriteret matrix
26: | Opdateringer | Delvis afsluttet | Flow, promotion, artifact-bind, rollback og katalogfelter har nu hjælpetekst; visuel E2E mangler. |
35: ## Verifikationsplan

## Dokumentation/Codex_REVIEW_Claude_Arkitektur_Risk_Test_2026-07-15.md

1: # Codex review af Claudes arkitektur-, risk- og testmateriale
8: ## 1. Samlet konklusion
14: ## 2. Arkitekturfeedback
16: ### Det bør vedtages
20: 3. ADR'er, route-auth-kontrol og ratchet-gates bør være bindende for både mennesker og AI-sessioner.
23: ### Det skal skærpes
25: 1. **IEC 62443-zoner:** Separate processer/vhosts på samme Mac er kun logisk segmentering, ikke en stærk zonegrænse. Arkitekturen skal for hver conduit angive enforcement point, tilladte flows, identitet, protokol, kryptering, logging og målrettet security level. Kompromittering af host/root krydser alle lokale zoner.
28: 4. **Scopekontrol:** Generisk edge-platform er strategisk relevant, men må ikke forsinke TimeLapse Pro production readiness. Første ADR bør fastlåse interface og grænser; implementér kun det, der reducerer aktuel monolit eller er nødvendigt for kamerapayloaden.
29: 5. **Headend-topologi:** Målbilledet mangler federation for flere prod-headends/kundestyrede headends: trust root, release promotion, tenant ownership, central vs. lokal CMDB, revocation, SBOM/VEX-distribution og evidensretur.
30: 6. **AI/GDPR:** Ollama/Open WebUI skal modelleres som separate dataflows og workloads. Billedtagging er en produktfunktion; Open WebUI er et privilegeret adminværktøj. Angiv formål, datakategorier, retention, model-loading/resource policy, cloud-escalation og underdatabehandlergrænse.
32: ## 3. Risk- og pentestfeedback
35: 2. Risikoscorerne bør have dokumenteret metode: asset/business attribute, trussel, sårbarhed, likelihood, impact, inherent risk, kontrol, residual risk, risk owner, treatment deadline og acceptance authority. Det vil gøre SABSA-sporbarheden revisionsbar.
36: 3. R22 skal stå “implemented, awaiting commit/deploy verification”, ikke endeligt lukket endnu. Samme gælder R23/R24.
38: 5. R25 om MFA-disable er velbegrundet og bør behandles P1 før Internet-go-live sammen med en generel step-up-policy for password, tokens, break-glass og key operations.
39: 6. Memory/SIEM bør tilføjes som availability/operability-fund: 49 flappende RAM-events på 24 timer, model-RSS ca. 6,8 GB og manglende workload lifecycle. Det er ikke et klassisk pentestfund, men relevant for SABSA Availability/Manageability og CRA robusthed.
41: ## 4. Testdokumentation
43: ### Korrekt
50: ### Skal ændres
52: 1. Integrationstests må ikke mutere et delt R&D-system som fast CI-mål. Brug isoleret PostgreSQL-schema/database, midlertidigt filområde, seedede identiteter og en ephemeral Headend-instans. Hardware-E2E mod R&D Edge er en separat, serialiseret suite.
53: 2. Integration må gerne være ikke-blokerende under etablering, men skal gate promotion til staging/prod, når baseline er grøn. Ellers bliver røde tests permanent ignoreret.
54: 3. Markører skal anvendes konsekvent pr. testfil/test. Den nuværende suite kan ikke sikkert opdeles alene via `-m`, og samlet collection fejler aktuelt på manglende deps/import-layout.
55: 4. CI skal bruge den understøttede Python-version (3.12), installere relevante dev/headend/edge testdependencies og bruge `--import-mode=importlib` eller unikke testmodulnavne. Lokal fuld collection fandt konkret: manglende `paramiko`, manglende `httpx`, `edge` import-path og to `test_drift_detection.py` med navnekollision.
57: 6. Coverageprocenter i dokumentet skal genereres som evidens fra CI; estimater som `~30%` og `~45%` må mærkes som estimater, ikke kontrolresultater.
59: ## 5. Anbefalet beslutning
61: Godkend arkitekturretningen som **målprincip**, med ovenstående seks skærpelser. Godkend ikke endnu dokumentet som implementeret target architecture eller som Internet-go-live-evidens. Næste arkitekturartefakter bør være:

## Dokumentation/Codex_Thumbnail_503_Analyse_2026-06-30.md

1: # Thumbnail-galleri: 503-storm (analyse + handlingsplan til Codex)
8: ## 1. Symptom
15: ## 2. Bekræftet: det er IKKE et manglende-fil-problem
25: ## 3. Rod-årsag: thundering herd + selvforstærkning → uvicorn/nginx-mætning
42:    b) upstream (uvicorn) backlog/timeout → nginx 503.
47: ## 4. Allerede bygget af Claude (på disk) — BEGGE lag, jf. Peters ønske
50: > backend-X-Accel-siden (flag-gated, default FRA). Codex mangler kun nginx-blokken +
71: ## 5. Codex' opgaver (infra) — den ægte fix, prioriteret
73: ### 5.1 Diagnose først (bekræft 503-kilden)
75: # Er der en rate-limit på /api/ i nginx?
77: # Hvordan startes uvicorn — hvor mange workers/tråde?
80: # Nginx-fejllog under en galleri-load (kig efter "limiting requests" / "upstream")
86: ### 5.2 Fixes
105: For at aktivere mangler KUN nginx-blokken + tre env-variable + genstart:
120: TIMELAPSE_XACCEL_PREFIX    = /_protected_media        # skal matche nginx-location ovenfor
122: (`TIMELAPSE_XACCEL_ROOT` SKAL være lig nginx-`alias`-roden; Python beregner filens sti
129: # Et thumbnail-svar skal nu komme fra nginx (ingen Python-stream). Bekræft headeren:
146: ### 5.3 Frontend gate (samtidighed + rate) — NU BYGGET (Claude)
153: ## 6. Anbefalet rækkefølge
157:    galleriet bør være brugbart MED DET SAMME, ingen genstart, ingen infra-ændring.
159:    Python-siden er færdig, der mangler kun nginx-blokken + 3 env-flag + genstart. Det fjerner
166: ## 7. Filer rørt (bygget af Claude, på disk)

## Dokumentation/Compliance-Readiness-Pack/00_INDEX.md

1: # TimeLapse Pro Compliance Readiness Pack
7: ## Formål
11: Pakken må ikke bruges som en erklæring om juridisk compliance eller certificering. Den er et readiness- og evidenslag: hvad kan TimeLapse Pro dokumentere nu, hvad skal udfyldes pr. kunde/site, og hvad skal lukkes før bredere production/markedskrav.
13: ## Dokumenter
25: ## Aktuel konklusion
27: TimeLapse Pro har et stærkt teknisk fundament for pilot- og kontrolleret production-readiness, men skal stadig undgå at formulere sig som certificeret eller fuldt juridisk compliant.
33: ## Autoritative interne kilder
44: ## Eksterne retskilder og standardkilder
46: Disse links er medtaget som officielle referencepunkter. ISO/IEC-standarder kræver legitim adgang til selve kontrolkataloget, hvis der senere skal laves clause-complete mapping.

## Dokumentation/Compliance-Readiness-Pack/01_CUSTOMER_SITE_DPIA_PACK.md

1: # Customer/Site DPIA Pack
4: **Vigtigt:** Ikke juridisk rådgivning. Kunden/dataansvarlig bør godkende formål, hjemmel, skiltning og opbevaringsperioder.
6: ## 1. Site cover sheet
22: ## 2. Behandling
34: ## 3. Nødvendighed og proportionalitet
44: | Kunde-SFTP er site-specifik | Delvist teknisk understøttet | Skal verificeres pr. site |
46: ## 4. Retention og disposition
52: | Auditlogs | Minimum sikkerheds-/driftsbehov; bør fastsættes kontraktuelt | |
56: ## 5. TV-overvågning/site-notice
58: Før installation skal kunden bekræfte:
66: Forslag til kort skiltetekst, der skal juridisk/kundemæssigt godkendes:
70: ## 6. Risk register pr. site
80: ## 7. Site approval

## Dokumentation/Compliance-Readiness-Pack/02_DATA_PROCESSING_ROLE_MATRIX.md

1: # Data Processing Role Matrix
6: ## 1. Standard rolleantagelse
13: | Tekniker | Autoriseret bruger på vegne af TLP | Skal være bundet til principal, grant, capability og audit |
15: ## 2. Datakategorier
27: ## 3. Subprocessor/service inventory
35: | Cloudflare/tunnel | Transport/UI access | Trafik afhænger af TLS-terminering | Skal bekræftes | Dokumenter TLS/termination/cache posture |
39: ## 4. Data subject request workflow
49: ## 5. Databrud og incident rolleflow
58: ## 6. Minimum DPA-indhold
60: En databehandleraftale bør mindst dække:

## Dokumentation/Compliance-Readiness-Pack/03_VULNERABILITY_UPDATE_SLA.md

1: # Vulnerability, Update And Support SLA
6: ## 1. Scope
17: ## 2. Vulnerability intake
22: | Debian/Armbian security | OS package checks | Mindst månedligt, før release |
23: | macOS/Homebrew | Headend package checks | Mindst månedligt, før release |
27: ## 3. Severity og target response
31: | Critical/P0 | Aktiv exploit, credential leak, remote code execution, data exposure | 24 timer | 72 timer eller risk-accepted workaround |
33: | Medium/P2 | Defense-in-depth gap, local privilege path, missing fail-closed test | 7 dage | 30 dage |
36: ## 4. Update policy
38: | Update type | Krav |
46: ## 5. Support period policy
48: For hver release skal følgende være deklareret i release evidence:
56: - required migrations.
58: ## 6. Coordinated vulnerability disclosure
62: > Sikkerhedsproblemer i TimeLapse Pro rapporteres til [security contact]. Rapporter bør indeholde påvirket komponent, version, reproduktion, potentiel impact og kontaktoplysninger. Vi bekræfter modtagelse, triagerer efter severity og koordinerer remediation og disclosure med rapportøren og berørte kunder.
74: ## 7. Release evidence gate

## Dokumentation/Compliance-Readiness-Pack/04_SBOM_RELEASE_EVIDENCE_CHECKLIST.md

1: # SBOM And Release Evidence Checklist
6: ## 1. Artifact identity
8: | Felt | Krav | Udfyldt |
19: ## 2. Integrity and signing
21: | Kontrol | Krav | Udfyldt |
27: | No `system-hash` production trust | Must fail closed | |
30: ## 3. SBOM/license
32: | Kontrol | Krav | Udfyldt |
38: | License classification | permissive / obligations / review / unknown / blocked | |
43: ## 4. Change governance
45: | Kontrol | Krav | Udfyldt |
55: ## 5. Edge-specific no-regression controls
57: For existing Edges, release must explicitly preserve:
69: ## 6. Evidence bundle output

