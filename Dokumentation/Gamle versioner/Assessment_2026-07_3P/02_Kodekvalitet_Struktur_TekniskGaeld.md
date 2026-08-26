# 02 — Kodekvalitet, Struktur, Memory & Teknisk Gæld

Commit: `eed9e3c8`.

## TPA-10 · **Høj** · Monolitten består: `main.py` = 18.541 linjer, 234 direkte routes + 19 routers

**Evidens:** `wc -l headend/main.py` = 18.541; ratchet-baseline (`tests/architecture_baseline.json`) fryser præcis dette tal. Ratchet-testene består (verificeret i rent miljø: 2 passed) — men baseline er kun et loft, ikke en nedtrapning.

**Vurdering:** Alt nyt ligger korrekt i routers/services (governance virker fremadrettet), men de 18.5k linjer indeholder stadig auth-flow, middleware, config, OTA, diagnostik og domænelogik i ét modul. Det er den største enkeltstående risiko for prod-drift (fejlisolering, reviewbarhed, onboarding).

**Anbefaling:** Gør ratchet til en *nedtælling*: sæt et kvartalsmål (fx −20% pr. release) og flyt i den rækkefølge, `06_Arkitekturvej…` beskriver (auth → settings → OTA → diagnostik). Ingen big-bang.

## TPA-11 · **Mellem** · 12+ daemon-baggrundstråde uden fælles supervision

**Evidens:** `headend/main.py:594-674` starter ved boot: uploads-, OS-bundle-, batch-, baseline-, backup-, debug-timeout-, retention-, thumbnail-loops m.fl.; dertil `siem.py:501`, `itim.py:792`, `importer.py:602`. Alle `daemon=True`, ingen fælles registry, health-eksponering eller restart-politik. 70 forekomster af tråd/loop-mønstre i alt.

**Risiko:** En død loop-tråd (f.eks. retention eller backup) opdages ikke af noget — jobbet udebliver bare stille. For prod er "stille manglende retention" et compliance-problem, ikke kun et driftsproblem.

**Anbefaling:** Lille `BackgroundJob`-registry: navn, sidste kørsel, sidste fejl, next-run — eksponeret i Drift-siden og i `/api/health`. Genstart ved crash med backoff. (Løser også observability-kravet i ITIM-designet.)

## TPA-12 · **Mellem** · Tråd-pr.-hændelse uden begrænsning

**Evidens:** `headend/main.py:4602` — `_enrich_exif` startes som ny tråd pr. kald (upload-flow).

**Risiko:** Under burst-upload (ny edge synkroniserer backlog) kan trådantal vokse ubegrænset → memory/scheduler-pres. Det er den mest sandsynlige "memory leak"-oplevelse i praksis, snarere end klassiske lækager.

**Anbefaling:** `ThreadPoolExecutor(max_workers=N)` (N i DB-settings), kø med backpressure, metrics på kø-dybde.

## TPA-13 · **Lav** · Module-level caches

**Evidens:** `headend/main.py:5739` `HEADEND_PLATFORM_MANUAL_PROFILES = {}` (ubegrænset dict). Sweep fandt ikke andre ubegrænsede module-caches i kritiske moduler.

**Anbefaling:** TTL/størrelsesgrænse eller flyt til DB-settings. Generelt: klassiske memory-lækager blev **ikke** fundet i sweep; den reelle risiko er trådene (TPA-11/12). En 48-timers soak-test på staging med memory-graf anbefales som evidens (indgår i handlingsplanen).

## TPA-14 · **Lav** · Deprecated FastAPI-mønstre

**Evidens:** 13 deprecation-warnings ved app-load: `@app.on_event("startup")` (`main.py:355`, `ai/settings_api.py:226` m.fl.) — deprecated til fordel for lifespan-handlers.

**Anbefaling:** Migrér til lifespan ved næste større ændring i opstartskoden (samtidig med TPA-11-registry — det er samme kodeområde). Ikke akut.

## TPA-15 · **Mellem** · Duplikation som fejlkilde

**Evidens:** Config-fingerprint-logik ×7 (TPA-03); settings-opslag implementeret både som `setting(db, …)` i main (53 brug) og lokale varianter i `itim.py`/`ai/*` med hver sin tabelfallback (TPA-04-filerne); to deploy-mapper (`deploy/` og `deployment/`); tre kilder til edge-image-stier (`main.py:14966-14967` + tools).

**Anbefaling:** Én settings-adapter, én fingerprint-funktion, én deploy-mappe. Duplikation er dyrere end monolitlinjer — det er dér "samme fejl tre gange"-klassen kommer fra.

## TPA-16 · **Lav** · Testsundhed

**Evidens:** 96 testfiler; ratchet + auth-sweep er de bærende gates. Auth-sweep er rød (TPA-01). `pytest.ini`-option `asyncio_default_fixture_loop_scope` kræver `pytest-asyncio` installeret — i et miljø uden den fejler *collection* i stedet for at skippe pænt.

**Anbefaling:** Kør governance-tests i CI på hver push (branch protection, jf. TPA-01); tilføj `pytest-asyncio` til requirements-dev (den mangler ikke i CI, men gør lokale kørsler skrøbelige).

## Samlet struktur-dom

Arkitekturretningen (ADR-001) er rigtig, governance-mekanikken findes og virker delvist, og kodehygiejnen er over gennemsnit (jf. positivlisten i 01). Gælden er koncentreret ét sted: monolitten + dens baggrundstråde. Det er godt nyt — den kan afvikles styret (dok. 06) uden at røre den fungerende edge.
