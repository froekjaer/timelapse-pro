# 06 — Arkitekturvej: Modulært Framework v1

Formål: en konkret, additiv vej til 1. version af det modulære framework, forankret i den empiri der er samlet i Mission Framework (REVIEW-001) og i den accepterede ADR-001. Dette er en *vej*, ikke en gen-design: retningen er allerede besluttet og bekræftet af flere uafhængige reviews.

## 0. Udgangspunkt (fakta)

ADR-001 (Accepted) definerer Platform/Payload-snit + `PayloadDriver` + capability manifest. REVIEW-001 producerede seks uafhængige reviews; konsensus på tværs (Claude, Z.ai, Kimi m.fl.): snittet er rigtigt, `contracts/` findes bare ikke endnu i koden, ADR-002 er uskrevet. Denne assessment bekræfter det samme fra kodesiden: monolitten (TPA-10) og dens tråde (TPA-11) er den konkrete gæld, snittet skal betale ned.

## 1. Princip for v1: kontrakten først, som tests — nul runtime-risiko

Første leverance er **ikke** kodeflytning. Det er `contracts/` (kontroplan `PayloadDriver`, dataplan med klassifikation, manifest med fail-closed-validering) landet som et rent, testet modul + arkitektur-gates i CI. Dette kan gøres uden at røre den kørende edge eller headend. (REVIEW-001's Claude-branch indeholder en kørbar reference-implementering med 20/20 tests, som kan bruges som skabelon — men som kode skal den genimplementeres mod jeres faktiske capture-flow, ikke kopieres.)

## 2. Rækkefølge (additiv, gate-styret) — headend først

Assessmentet skærper REVIEW-001-anbefalingen med et konkret kode-argument: **headend før edge**, fordi (a) edge allerede er halv-modulær (`edge/hal`, `edge/config`, `edge/tunnel`, `edge/update`), (b) monolittens 18.5k linjer + de usuperviserede tråde er den reelle risiko, og (c) auth/RBAC-udtræk fjerner samtidig `from main import get_current_user`-cirkularitetsmønsteret, som alle nye API-moduler nu kopierer (handover 2026-07-18 §retning).

| Fase | Indhold | Lukker fund |
|---|---|---|
| F1 | `contracts/` + arkitektur-gates (import-boundary, secure-router, hardkodet-sweep) som tests-only | grundlag; TPA-03/15 mønster |
| F2 | **Auth/RBAC-udtræk** fra `main.py` til `platform/control` bag authenticated-router-factory; ratchet → nedtælling | TPA-01, TPA-10 (start), cirkularitet |
| F3 | Baggrundsjob-registry (supervision/health) + settings-adapter | TPA-11, TPA-12, TPA-13, TPA-15, H-01..H-07 |
| F4 | Dataplan-wrapper med klassifikation over eksisterende SFTP-ingest + retention-supervision | GDPR-gap, TPA-11 |
| F5 | Edge agent/payload-split bag `PayloadDriver` + per-device-nøgle (SPIKE på rigtig Orange Pi) | TPA-02, TPA-00 (per-device), R05/R08 |
| F6 | Andet payload (simuleret, fx miljøsensor) som anti-koblingsbevis i CI | beviser platform-neutralitet |

## 3. Kontraktsæt v1 (anbefalet, minimalt)

Kontrolplan (`PayloadDriver`: configure/start/stop/health/handle_command — supervisor ejer liveness), dataplan (tre kanaltyper: blob/timeseries/event, hver med klassifikation + retention-klasse), manifest (capabilities/kvoter/allowlists, fail-closed valideret mod operatør-signeret nodepolicy). Ingen aktuator-capability i v1 (sikkerhedsport for fremtidige OT-payloads). Detaljeret normativ skitse: ADR-001 + REVIEW-001 Claude-branch ADR-CL-004.

## 4. Governance der gør frameworket selv-håndhævende (kritisk for én-mands-drift)

Alt det der ellers kræver menneskelig årvågenhed flyttes til maskinelle gates: import-boundary-test (platform importerer aldrig payload), secure-router-by-construction (auth-fejlklassen bliver umulig, ikke bare opdaget), hardkodet-sweep (03), ratchet som nedtælling, kendte-secrets-scan (TPA-00). CI med branch protection er forudsætningen — uden den er gates dekoration (jf. TPA-01, hvor gaten var rød og upåagtet).

## 5. Forhold til Mission-Platform-repoet

Empirien og de seks reviews lever i `froekjaer/Mission-Platform`. **Anbefaling:** byg frameworket *ind i* timelapse-pro additivt (som ADR-001 foreskriver: monorepo, timelapse som første payload) frem for at starte et parallelt system — et parallelt system ville betyde to kodebaser at drifte alene. Mission-Platform forbliver design-/empiri-arkiv og meta-review-grundlag; produktionskoden konvergerer mod samme kontrakter i timelapse-pro. Når/hvis et andet reelt payload kommer, kan platform-kernen udskilles som pakke (ADR-001 model B).

## 6. Næste sikre skridt (ét)

Land `contracts/` + de fire arkitektur-gates som tests-only på en branch, med branch protection aktiveret. Nul runtime-risiko, beskytter alt efterfølgende arbejde, og er det fælles fundament både denne assessment, ADR-001 og REVIEW-001-konsensus peger på.
