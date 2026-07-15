# Codex review af Claudes arkitektur-, risk- og testmateriale

**Dato:** 2026-07-15  
**Reviewer:** Codex  
**Dokumenter:** `Claude_QA_Arkitektur_Review_2026-07-15.md`, `RISK_ASSESSMENT_v11_ADDENDUM_2026-07-15.md`, `MASTER_TEST_CHECKLIST_v1.md` v1.2  
**Status:** Faglig feedback til indarbejdelse; ændrer ikke alene godkendelsesstatus.

## 1. Samlet konklusion

Materialet er gennemarbejdet og identificerer korrekt de største aktuelle risici: gentagne auth-fejl ved router-mount, voksende monolit, manglende CI-assurance og behovet for et Platform/Payload-snit. Konklusionen **LAB/pre-production, ikke Internet-facing production-klar** er understøttet.

R22/R23 er verificeret og rettet lokalt. R24 er efterfølgende rettet ved at skille `/translations` ud som autentificeret viewer-route, mens mutationer og review forbliver admin/super-admin. De er først lukkede i governance-forstand efter commit, CI, deploy og runtime-evidens.

## 2. Arkitekturfeedback

### Det bør vedtages

1. Ingen nye endpoints i `headend/main.py`; brug `api/router`, `service` og `models` med kontrakttest før flytning.
2. Platform/Payload-snittet er rigtigt. Kamera/capture/AI er første payload; enrollment, identitet, config, update, telemetri og tunnel er platform.
3. ADR'er, route-auth-kontrol og ratchet-gates bør være bindende for både mennesker og AI-sessioner.
4. Additiv migration er rigtig: eksisterende camera/capture-kontrakter må ikke omdøbes bredt nu.

### Det skal skærpes

1. **IEC 62443-zoner:** Separate processer/vhosts på samme Mac er kun logisk segmentering, ikke en stærk zonegrænse. Arkitekturen skal for hver conduit angive enforcement point, tilladte flows, identitet, protokol, kryptering, logging og målrettet security level. Kompromittering af host/root krydser alle lokale zoner.
2. **Reverse SSH:** Formuleringen “ingen indgående forbindelser til Edge” er kun korrekt på transport/firewall-niveau. Tunnelen er en bidirektionel management-conduit, som kan føre kommandoer ind i OT-zonen. Den kræver JIT-ticket, destinations-/port-allowlist, kortlivede certifikater, session recording, kill switch og eksplicit kundegodkendelse.
3. **Platform/Payload-isolation:** Et `PayloadDriver`-interface er ikke nok. Definér capability manifest, signerede payloadpakker, versionskontrakt, resource quota, least-privilege service identity, fil-/netværksallowlist, health/rollback og telemetrisk attribution pr. payload.
4. **Scopekontrol:** Generisk edge-platform er strategisk relevant, men må ikke forsinke TimeLapse Pro production readiness. Første ADR bør fastlåse interface og grænser; implementér kun det, der reducerer aktuel monolit eller er nødvendigt for kamerapayloaden.
5. **Headend-topologi:** Målbilledet mangler federation for flere prod-headends/kundestyrede headends: trust root, release promotion, tenant ownership, central vs. lokal CMDB, revocation, SBOM/VEX-distribution og evidensretur.
6. **AI/GDPR:** Ollama/Open WebUI skal modelleres som separate dataflows og workloads. Billedtagging er en produktfunktion; Open WebUI er et privilegeret adminværktøj. Angiv formål, datakategorier, retention, model-loading/resource policy, cloud-escalation og underdatabehandlergrænse.

## 3. Risk- og pentestfeedback

1. Addendumformatet er korrekt; tidligere fund må ikke markeres re-verificeret, når dokumentet selv siger “ikke re-verificeret”. Vis særskilt `inherited`, `verified_at`, `evidence` og `control owner`.
2. Risikoscorerne bør have dokumenteret metode: asset/business attribute, trussel, sårbarhed, likelihood, impact, inherent risk, kontrol, residual risk, risk owner, treatment deadline og acceptance authority. Det vil gøre SABSA-sporbarheden revisionsbar.
3. R22 skal stå “implemented, awaiting commit/deploy verification”, ikke endeligt lukket endnu. Samme gælder R23/R24.
4. VPEN er korrekt benævnt virtuel/code-assisted test. Den erstatter ikke DAST, ekstern scanning, authz-matrix-test, dependency/container scanning eller restore-/rollback-test.
5. R25 om MFA-disable er velbegrundet og bør behandles P1 før Internet-go-live sammen med en generel step-up-policy for password, tokens, break-glass og key operations.
6. Memory/SIEM bør tilføjes som availability/operability-fund: 49 flappende RAM-events på 24 timer, model-RSS ca. 6,8 GB og manglende workload lifecycle. Det er ikke et klassisk pentestfund, men relevant for SABSA Availability/Manageability og CRA robusthed.

## 4. Testdokumentation

### Korrekt

- Opdelingen unit/contract/integration/E2E er nødvendig.
- De aktuelle tal 38 filer i `tests/` og 11 i `headend/tests/` er verificeret.
- UI har ingen egne applikationstests; build/lint er ikke funktionel UI-test.
- Edge-, auth-, update-, AI- og restoreområderne er korrekt prioriteret.

### Skal ændres

1. Integrationstests må ikke mutere et delt R&D-system som fast CI-mål. Brug isoleret PostgreSQL-schema/database, midlertidigt filområde, seedede identiteter og en ephemeral Headend-instans. Hardware-E2E mod R&D Edge er en separat, serialiseret suite.
2. Integration må gerne være ikke-blokerende under etablering, men skal gate promotion til staging/prod, når baseline er grøn. Ellers bliver røde tests permanent ignoreret.
3. Markører skal anvendes konsekvent pr. testfil/test. Den nuværende suite kan ikke sikkert opdeles alene via `-m`, og samlet collection fejler aktuelt på manglende deps/import-layout.
4. CI skal bruge den understøttede Python-version (3.12), installere relevante dev/headend/edge testdependencies og bruge `--import-mode=importlib` eller unikke testmodulnavne. Lokal fuld collection fandt konkret: manglende `paramiko`, manglende `httpx`, `edge` import-path og to `test_drift_detection.py` med navnekollision.
5. Tilføj mindst: route-auth matrix, tenant isolation, Open WebUI lifecycle/model-unload/tagging-resume, SIEM anti-flap, signed artifact rollback/receipt, backup restore, thumbnail idempotens/performance og Playwright for kritiske UI-flows.
6. Coverageprocenter i dokumentet skal genereres som evidens fra CI; estimater som `~30%` og `~45%` må mærkes som estimater, ikke kontrolresultater.

## 5. Anbefalet beslutning

Godkend arkitekturretningen som **målprincip**, med ovenstående seks skærpelser. Godkend ikke endnu dokumentet som implementeret target architecture eller som Internet-go-live-evidens. Næste arkitekturartefakter bør være:

1. ADR-001 Platform/Payload og scopegrænse.
2. IEC 62443 zone/conduit-register med SL-T og håndhævelsespunkter.
3. ADR-002 Headend federation/release trust.
4. Test Architecture v1 med ephemeral CI, hardware-E2E og promotion gates.
5. Opdateret SABSA traceability fra business attributes til kontroller og evidens.

