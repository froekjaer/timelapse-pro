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

## 5. Agent-adgangspolitik — BESLUTTET, permanent (2026-07-05)

**Peter, ordret:** "Hverken Codex eller dig har eller vil få adgang til staging og Prod. Kun
vores R&D udviklingssystem."

Dette er nu en fast, permanent politik, ikke en midlertidig tilstand eller noget der revurderes
ved go-live:

- **Claude og Codex arbejder KUN på `rd`** (nuværende Mac Mini). Ingen undtagelser, ingen "kun
  til et engangstjek".
- **`staging` og `prod` er 100% Peters (og evt. fremtidige menneskelige kollegers) domæne.**
  Ingen agent-SSH-nøgler, deploy-keys, API-tokens eller lignende må nogensinde oprettes for disse
  miljøer. Dette lukker det tidligere åbne spørgsmål #3 (staging-agent-adgang: **nej**, samme
  regel som prod) og gør R19 i `RISK_ASSESSMENT_v10.md` til en bekræftet, håndhævet politik i
  stedet for en anbefaling.
- **Praktisk konsekvens:** installationer på `staging`/`prod` skal kunne udføres af Peter ALENE,
  uden agent-assistance i selve udførelsen. Det er baggrunden for
  `INSTALLATION_GUIDE_HEADEND_v1.md`/`deploy/install/install_headend.sh` (§6) — de skal være
  udførlige/robuste nok til at stå alene, da Claude/Codex ikke kan fejlsøge live på de maskiner.
- Codex' `AgentPrincipal`/miljøflag-model (agent/service-principal-forslaget) er stadig relevant
  som en TEKNISK, defense-in-depth-håndhævelse af denne politik (i tilfælde af fejlkonfiguration
  eller fremtidige nye agenter) — men politikken gælder allerede nu, uafhængigt af om/hvornår den
  kode skrives.

## 6. Øvrige åbne beslutninger

1. **Kan staging-iMac'en håndtere den fulde stack?** — kapacitetstest udestår (Postgres + headend
   + nginx, evt. Ollama). Hvis ikke: overvej reduceret staging-scope (kun headend+DB, uden AI) eller
   andet hardware.
2. **Bekræft ingen eksisterende agent-/deploy-credentials på den fremtidige prod-maskine** — den
   kører allerede CrushFTP/legacy i dag; ingen SSH-nøgle, deploy-key eller lignende bør nogensinde
   have eksisteret der for Claude/Codex.
4. **Verificér Kirkbi A/S-databehandleraftalens dækning** mod den faktiske nuværende tekniske
   behandling (se §4).
5. **`AgentPrincipal`/miljøflag-modellen** kan nu designes præcist til to håndhævede miljøer
   (`rd` tilladt, `staging`+`prod` for evigt forbudt for agenter) — enklere end oprindeligt
   antaget, da der ikke er noget "måske" tilbage for `staging`.

## 7. Styresystem og Cloudflare-arkitektur (afklaret 2026-07-05)

- **OS:** macOS på både `staging` (ældre iMac) og `prod`, samme som `rd` i dag. Historisk startede
  headend på en Raspberry Pi 5 (nu helt udfaset). Fremtidig Linux-understøttelse er ikke udelukket,
  men er bevidst IKKE en del af scope nu — tages op hvis/når det bliver relevant.
- **Cloudflare Tunnel undgås bevidst** (Peters eksplicitte, tidligere aftalte valg) — se §8.

## 8. KORREKTION — Cloudflare Tunnel er IKKE målarkitekturen for prod

Store dele af `GO_LIVE_CHECKLIST_v10.md` §A og `RISK_ASSESSMENT_v10.md`s zone-model (samt
`NGINX_CLOUDFLARE_MIGRATION_LAB_v1.md`) har hidtil antaget at vejen til go-live går via
Cloudflare Tunnel (`cloudflared`, nul åbne indgående porte). **Peter har bekræftet at dette IKKE
er den ønskede prod-arkitektur** — Cloudflare Tunnel skal undgås. Dette er allerede reflekteret i
det statiske marketingsite, der er bygget (`www/index.html`): en almindelig offentlig
`www.timelapse-pro.dk`, med login-knapper der peger direkte på `https://backend.timelapse-pro.dk/`
— dvs. almindelig direkte HTTPS-eksponering (standard port 443, ægte Let's Encrypt-certifikat,
hostname-baseret nginx-routing), samme mønster som den NUVÆRENDE `rd`-nginx-config
(`deploy/nginx/timelapse.froekjaer.dk.conf`) allerede bruger — ikke `cloudflared` på et
loopback-baseret 18443-mønster.

**Konsekvens for CA/mTLS-designet (#52):** Dette gør Model B ("ende-til-ende mTLS til
nginx/Headend selv", `Claude_Intern_CA_mTLS_Design_2026-07-05.md` §6) til det naturlige valg
fremfor Model A (Cloudflare Access mTLS), da der slet ikke skal være nogen Cloudflare Tunnel i
vejen. Se opdateret §6/§10 i det dokument.

**Bemærk:** dette ændrer ikke nødvendigvis noget for `rd`-domænet (`timelapse.froekjaer.dk`),
som er internt/agent-/Peter-vendt, ikke kundevendt og ikke en go-live-blocker — `rd` kan fortsat
bruge Cloudflare (DNS/evt. proxy) som i dag, uafhængigt af prod-beslutningen. §A i
`GO_LIVE_CHECKLIST_v10.md` og VPEN-2026-001 er opdateret til at beskrive den korrekte
prod-målarkitektur (se de dokumenter for detaljer).

Ingen kode er ændret som følge af dette dokument — det er en topologi-/beslutningsafklaring, der
fodrer det videre arbejde med agent-adgangsmodellen og installationsscriptet (se `HANDOVER_LOG.md`
2026-07-05).
