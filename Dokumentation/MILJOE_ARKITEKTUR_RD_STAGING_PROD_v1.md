# TimeLapse Pro — Miljøarkitektur: R&D/Test, Staging, Produktion (v1)

**Dato:** 2026-07-05 · **Kilde:** Peters afklaring i `HANDOVER_LOG.md` som svar på Codex'
agent/service-principal-forslag (2026-07-05).
**Status:** Topologi og terminologi besluttet af Peter. Staging-serverens kapacitet er ikke
bekræftet. Agent-adgangsmodellen (Codex' `AgentPrincipal`-forslag) er fortsat under diskussion —
se `HANDOVER_LOG.md`.

Dette dokument er den kanoniske beskrivelse af de tre miljøer og deres formål. Driftsdetaljer
(services/porte/genstart) for det nuværende R&D-system står fortsat i
`SERVICES_OG_DRIFT_kilde_til_sandhed.md` — dette dokument beskriver kun TOPOLOGIEN og
adskillelsen mellem miljøerne, ikke drift af det enkelte system.

---

## 1. De tre miljøer

### R&D/Test (`rd`) — nuværende system, `timelapse.froekjaer.dk`
Det system Claude og Codex arbejder på i dag (Mac Mini, se `SERVICES_OG_DRIFT_kilde_til_sandhed.md`).
- **Tilknyttet edge-enhed:** Kunde "Frøkjær" (Peter selv) — reel, aktiv enhed, men ejet af Peter,
  ikke en ekstern kunde. Bruges som daglig testenhed (~144 billeder/døgn, atypisk tæt placering).
- **Testkunder uden data:** oprettet til strukturtest (roller, RBAC, tenant-adskillelse), ingen
  reelle billeder.
- **Kunde Kirkbi A/S, Site "Travbyen":** billeder importeret fra et andet (legacy) timelapse-
  system, så der findes et realistisk datasæt at arbejde med. Dette er IKKE en syntetisk
  testkunde uden reelt grundlag — Travbyen er et site tilhørende en rigtig kunde (Kirkbi A/S), og
  **der findes allerede en databehandleraftale med Kirkbi A/S** (bekræftet af Peter 2026-07-05).
  Se §4 nedenfor for hvad det betyder for GDPR-status. Travbyen-data er også udpeget som
  **fremtidig stagingdata** (§1 Staging).
- **Agent-adgang i dag:** Claude og Codex arbejder bredt her (kode, konfiguration, i praksis også
  data), som hidtil. Dette er selve formålet med miljøet.

### Staging — ny 3. server (planlagt)
- Fysisk allerede til stede: en ældre iMac Peter har i huset. Kapaciteten er **ikke bekræftet** —
  det skal afklares om den kan køre den fulde stack (Postgres + headend + nginx, evt. Ollama).
- **Formål:** software-parity med prod. Der installeres bevidst KUN det samme softwarelag som på
  prod-maskinen (samme OS-pakker/versioner, ingen af R&D-miljøets ekstra værktøjer), så
  sameksistens-/versionsproblemer opdages FØR de rammer prod, ikke efter.
- **Data:** Travbyen-datasættet genbruges som stagingdata (allerede importeret, allerede dækket af
  en databehandleraftale — praktisk og lav-risiko valg).
- **Agent-adgang:** ikke besluttet endnu — flagget som åbent spørgsmål i §5.

### Produktion (`prod`) — fremtidigt system, `timelapsepro.dk`
- **Helt andet fysisk system** end R&D-Mac Mini'en og staging-iMac'en.
- **Kører allerede i dag** — inden TimeLapse Pro overhovedet er deployet dertil — CrushFTP, brugt
  til (a) udveksling af kundedata og (b) det eksisterende legacy timelapse-system, som TimeLapse
  Pro skal erstatte. Se §3 for hvorfor dette har betydning NU, ikke først ved cutover.

---

## 2. Terminologi (afklarer navnekollisionen fra Codex-forslaget)

Codex' oprindelige forslag brugte `lab`/`rd`/`test` som mulige miljønavne. Problem: ordet **"lab"
er allerede optaget** i kodebasen til noget andet — `debug_mode.enabled`/"lab mode" er en
PER-KAMERA tuning-tilstand (se `RISK_ASSESSMENT_v10.md` R17), ikke et systemmiljø. At genbruge
samme ord til systemmiljøet ville skabe reel forvekslingsrisiko.

**Besluttet nøgleterminologi** (til DB/env/kode, hvis/når det bliver relevant):

| Nøgle (kode/DB) | UI-visning | Fysisk system |
|---|---|---|
| `rd` | "R&D/Test" | Mac Mini, `timelapse.froekjaer.dk` (nuværende) |
| `staging` | "Staging" | iMac (planlagt, kapacitet ikke bekræftet) |
| `prod` | "Produktion" | Nyt/andet fysisk system, `timelapsepro.dk` (planlagt) |

Kamera-tilstanden bevarer sit eksisterende navn **"lab mode"** (`debug_mode.enabled`) uændret —
det er et andet koncept (kamera-tuning) og bør ikke omdøbes for at undgå at bryde eksisterende
UI-tekst/dokumentation (R17).

---

## 3. Hvorfor prod-isolation haster mere end en "senere" opgave

Den oprindelige antagelse i Codex-forslaget var, at prod-isolation primært handler om at
forhindre agent-adgang til en FREMTIDIG launch. Peters afklaring ændrer dette billede: prod-
maskinen håndterer **allerede i dag** rigtige kunders data via CrushFTP og det udfasende legacy-
system. Det betyder:

- Ingen agent-credentials (SSH-nøgler, deploy-keys, API-tokens) må nogensinde have eksisteret på
  eller haft adgang til den maskine — hverken i dag eller i fremtiden.
- Dette bør **bekræftes eksplicit**, ikke antages ud fra "vi har jo ikke arbejdet med den endnu".
  Se åbent spørgsmål #2 i §5.
- Når TimeLapse Pro rent faktisk deployes til `timelapsepro.dk`, kommer den til at køre side om
  side med CrushFTP og (i en overgangsperiode) det legacy-system, den skal erstatte — hvilket er
  en yderligere grund til at have staging som en reel parity-test af hele stakken FØR cutover,
  ikke kun af TimeLapse Pro-koden isoleret.

---

## 4. GDPR-status opdateret med Kirkbi A/S-fundet

`RISK_ASSESSMENT_v10.md` R12 / `GO_LIVE_CHECKLIST_v10.md` G-03 har hidtil listet "databehandler-
aftale" som en fuldstændig blocker (🔴, "ikke startet"). Det er nu **delvist unøjagtigt**: der
findes allerede en databehandleraftale med **Kirkbi A/S** (kunden bag Travbyen-billederne),
bekræftet af Peter 2026-07-05.

**Codex' præcisering (2026-07-05, værdifuld — fastholdes her):** Dette fjerner en vigtig
uklarhed, men er ikke i sig selv det samme som fri R&D-agentadgang til alle kundedata. Tre
adskilte spørgsmål skal holdes fra hinanden:
1. **Lovligt behandlingsgrundlag for drift/support** — dækket for Kirkbi A/S af den eksisterende
   aftale (med forbehold nedenfor).
2. **AI-agenters (Claude/Codex) adgang til reelle kundebilleder til udvikling/QA** — et separat
   spørgsmål, som en drifts-DPA ikke nødvendigvis besvarer. Bør afklares eksplicit, ikke antages.
3. **Fremtidig prod-afskærmning**, så Codex/Claude aldrig kan nå `timelapsepro.dk` — se §3/R19,
   uafhængigt af DPA-status.

**Vigtigt forbehold (ikke en frigivelse af blockeren, kun en præcisering):** en eksisterende
aftale, indgået i forbindelse med det ORIGINALE legacy-system, dækker ikke nødvendigvis
automatisk den behandling, TimeLapse Pro reelt udfører i dag — fx AI/Gemini cloud-eskalering
(behandling hos en tredjepart-underdatabehandler), GPS/lokationsmetadata, eller AI-agenters
adgang til billeddata (punkt 2 ovenfor). **Anbefaling:** få verificeret (Peter, evt. med juridisk
bistand) om den eksisterende Kirkbi-aftale reelt dækker disse behandlingsformer, før den bruges
som fuld evidens for G-03. Nye kunder ud over Kirkbi A/S kræver under alle omstændigheder deres
egen aftale, jf. DPIA-skabelonen.

---

## 5. Åbne beslutninger

1. **Kan staging-iMac'en håndtere den fulde stack?** — kapacitetstest udestår (Postgres + headend
   + nginx, evt. Ollama). Hvis ikke: overvej reduceret staging-scope (kun headend+DB, uden AI) eller
   andet hardware.
2. **Bekræft ingen eksisterende agent-/deploy-credentials på den fremtidige prod-maskine** — den
   kører allerede CrushFTP/legacy i dag; ingen SSH-nøgle, deploy-key eller lignende bør nogensinde
   have eksisteret der for Claude/Codex.
3. **Skal staging have agent-adgang?** Hvis ja: med hvilken rettighed, og skal det logges/
   audit-spores på samme måde som `rd` (se Codex' agent/service-principal-forslag)?
4. **Verificér Travbyen-databehandleraftalens dækning** mod den faktiske nuværende tekniske
   behandling (se §4).
5. **Skal `AgentPrincipal`/miljøflag-modellen (Codex' forslag) implementeres for alle tre miljøer
   samtidig, eller først for `rd`+`prod` og siden udvidet til `staging` når den er sat op?** —
   Claudes anbefaling: design modellen generisk nok til tre miljøer fra start (billigere end at
   eftermontere), men implementér/aktivér kun `rd`/`prod`-håndhævelsen først, da `staging` endnu
   ikke findes som kørende system.

Ingen kode er ændret som følge af dette dokument — det er en topologi-/beslutningsafklaring, der
fodrer det videre arbejde med agent-adgangsmodellen (se `HANDOVER_LOG.md` 2026-07-05).
