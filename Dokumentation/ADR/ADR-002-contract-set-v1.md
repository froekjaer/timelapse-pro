# ADR-002: Contract set v1 — the modular framework seam (control, data, manifest)

- **Status:** Proposed (tests-only landing; no runtime wiring yet)
- **Dato:** 2026-07-31 · **Forfatter:** Claude · **Bygger på:** ADR-001 (Accepted 2026-07-16), REVIEW-001-konsensus, `Assessment_2026-07_3P/06_Arkitekturvej_Modulaert_Framework_v1.md`

## Kontekst

ADR-001 vedtog Platform/Payload-snittet og lovede en ADR-002 for kontraktdetaljerne — den blev aldrig skrevet, og `contracts/` fandtes ikke i koden (bekræftet i 3P-assessmentet, O-01/§6). Uden en konkret, versioneret kontrakt-flade forbliver snittet en hensigt, og monolitten (18.541 linjer) vokser mod ingen defineret grænse. Dette er "næste sikre skridt": land kontrakten som ren, testet kode + arkitektur-gates, uden at røre kørende edge/headend.

## Beslutning

Indfør pakken `contracts/` med tre uafhængigt SemVer'ede kontrakter:

1. **Control (`PayloadDriver`)** — `configure/start/stop/health/handle_command`. Supervisor ejer liveness; driveren ejer sin egen kadence. (Bevidst uden `tick(now)` fra ADR-001-skitsen: reelle payloads har uforenelige kadencer — jf. REVIEW-001 ADR-CL-004.)
2. **Data (`DataSink` + tre kanaltyper: blob/timeseries/event)** — hver kanal bærer klassifikation + retention-klasse, så GDPR-retention bliver mekanisme, ikke dokumentation. Persondata kun på blob-kanaler i v1.
3. **Manifest (fail-closed)** — capabilities/kvoter/allowlists/kanaler, valideret fail-closed; ukendt felt/capability/enum/kvote-overskridelse → afvis. **Ingen aktuator-capability i v1** (sikkerhedsport for fremtidige OT-payloads; at tilføje én er et bevidst major-bump med sikkerhedsreview).

**Rene invarianter, maskinelt håndhævet** (`tests/test_contracts_architecture.py`): `contracts/` importerer intet fra `headend/`/`edge/`/`main`; manifest fejler closed; ingen aktuator i v1.

**Konfigurationsdisciplin operationaliseret** (`tests/test_hardcoded_ratchet.py`): hardkodede infra-værdier i `headend/`+`edge/` må kun falde (baseline 105) — nye fejler CI; hver flytning til DB-settings/UI sænker baseline. Dette håndhæver reglen "alt konfigurerbart i UI+DB, kun opstartsparametre i .env" (3P-assessment dok. 03).

## Hvorfor tests-only nu?

Nul runtime-risiko: intet i produktion importerer `contracts/` endnu. Pakken er målet, som P2-01-udtræk migrerer *mod* (auth/RBAC først, jf. arkitekturvejen). At lande kontrakten før flytningen betyder at hver senere udtræksflytning sker mod en aftalt, testet grænse i stedet for ad hoc.

## Alternativer

- **Vente til udtræk begynder.** Afvist: så flyttes kode mod en udefineret grænse (præcis hvordan monolitten opstod).
- **gRPC/protobuf nu.** Afvist: toolchain-vægt før et andet sprog findes; ABC'er + JSON-schema er transport-agnostiske og kan projiceres til protobuf senere.

## Konsekvenser

Positive: fælles, versioneret, maskin-bevogtet flade fra dag ét; to nye CI-gates der beskytter alt fremtidigt arbejde; direkte fremdrift på "1. version af det modulære framework". Negative: SemVer-disciplin på `contracts/` er nu reel omkostning (accepteret som prisen for OT-optionen). Reversibelt: rent additivt; kan fjernes uden at røre kørende kode.

## Valideringsvej

11 tests grønne (kontrakt-renhed, manifest fail-closed ×6, policy-check, ingen-aktuator, versioner, hardkodet-ratchet). Næste skridt (separat): implementér en `SpoolDataSink` + supervisor og wrap den eksisterende kameralogik bag `PayloadDriver` som vertical slice — bevist muligt i REVIEW-001 (20/20 tests), skal genimplementeres mod den faktiske capture-kode. **➡️ Peter:** aktivér branch protection så de nye gates ikke kan omgås.
