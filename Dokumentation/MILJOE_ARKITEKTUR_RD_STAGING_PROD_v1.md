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
2. **AI-agenters (Claude/Codex) adgang til reelle kundebilleder til udvikling/QA** — **BESVARET
   2026-07-05 (Peter):** der er, ud over selve databehandleraftalen, givet EKSPLICIT tilladelse
   til at Travbyen-billederne anvendes i forbindelse med udviklingen af TimeLapse Pro. Dette
   lukker punkt 2 specifikt for udviklingsformål (Claude/Codex' nuværende R&D-arbejde på disse
   billeder er dermed udtrykkeligt dækket, ikke kun antaget). Det dækker ikke automatisk andre,
   fremtidige anvendelsesformål (fx offentlig markedsføring af billederne) — kun udvikling.
3. **Fremtidig prod-afskærmning**, så Codex/Claude aldrig kan nå `timelapsepro.dk` — se §3/R19,
   uafhængigt af DPA-status.

**Vigtigt forbehold (ikke en frigivelse af blockeren, kun en præcisering):** en eksisterende
aftale, indgået i forbindelse med det ORIGINALE legacy-system, dækker ikke nødvendigvis
automatisk den behandling, TimeLapse Pro reelt udfører i dag — fx AI/Gemini cloud-eskalering
(behandling hos en tredjepart-underdatabehandler) eller GPS/lokationsmetadata. AI-agenters
udviklingsadgang til billeddata (punkt 2 ovenfor) er nu udtrykkeligt tilladt separat fra selve
databehandleraftalen. **Anbefaling:** få verificeret (Peter, evt. med juridisk bistand) om den
eksisterende Kirkbi-aftale reelt dækker AI/Gemini-behandlingen og GPS-metadata, før den bruges
som fuld evidens for G-03. Nye kunder ud over Kirkbi A/S kræver under alle omstændigheder deres
egen aftale OG en tilsvarende eksplicit udviklings-tilladelse, jf. DPIA-skabelonen.

---

## 5. Agent-adgangspolitik — default-deny, med kontrolleret undtagelse (opdateret 2026-07-06)

**Peter, ordret (2026-07-05):** "Hverken Codex eller dig har eller vil få adgang til staging og
Prod. Kun vores R&D udviklingssystem."

**Peter, ordret (2026-07-06, uddybning):** "Jeg tænker vi (trods min tidligere udtalelse) skal
have en kontrolleret og logget adgangsmulighed for dig (Codex) til support adgang, som kan
anvendes i forbindelse med installation og fejlsøgning/fejlretning."

Dette er en modning, ikke en modsigelse, af 2026-07-05-beslutningen: **standardtilstanden er
uændret ingen stående agent-adgang** — men der findes nu en dokumenteret, kontrolleret
undtagelsesvej ("break-glass"), i stedet for et absolut "aldrig, ingen undtagelser". Fuldt design:
`Claude_Support_Access_Model_2026-07-06.md`.

- **Standard: Claude og Codex arbejder KUN på `rd`** (nuværende Mac Mini). Ingen stående adgang
  til `staging`/`prod` for nogen af agenterne, hverken normalt eller "til et engangstjek".
- **Undtagelse: kontrolleret, tidsbegrænset support-adgang** kan aktiveres af Peter ALENE, pr.
  session, til installation eller fejlsøgning/fejlretning på `staging`/`prod`. Gælder BEGGE
  agenter (Claude og Codex). Teknisk mekanisme: korttidslevende SSH-brugercertifikat udstedt af
  en separat Support-CA (ikke device-CA'en fra #52-designet), med udløb indbygget kryptografisk
  ved udstedelsen — ikke en efterfølgende manuel oprydning. Hver aktivering respekterer et
  kunde-samtykke-tjek (hvilken kunde har data på maskinen, og er support-adgang dækket af DPA'en
  implicit eller kræver et eksplicit "ja" for netop denne session) og genererer et signeret
  ticket, logget til audit — se `Claude_Support_Access_Model_2026-07-06.md` §5-6 for det fulde
  design.
- **Ingen agent kan selv anmode om eller udstede denne adgang** — kun Peter kan aktivere den.
  Dette lukker det tidligere åbne spørgsmål #3 (staging-agent-adgang: standard **nej**, samme
  regel som prod, men nu med en dokumenteret undtagelsesproces) og opdaterer R19 i
  `RISK_ASSESSMENT_v10.md` fra "ingen undtagelser" til "kontrolleret undtagelsesproces, ikke
  endnu bygget".
- **Praktisk konsekvens uændret for det almindelige tilfælde:** installationer på `staging`/`prod`
  skal fortsat primært kunne udføres af Peter ALENE — `INSTALLATION_GUIDE_HEADEND_v1.md`/
  `deploy/install/install_headend.sh` forbliver udførlige nok til at stå alene. Support-adgangen
  er en undtagelse til brug ved behov, ikke en erstatning for selvstændig drift.
- Codex' `AgentPrincipal`/miljøflag-model (agent/service-principal-forslaget) er fortsat relevant
  som en TEKNISK, defense-in-depth-håndhævelse af default-deny (i tilfælde af fejlkonfiguration
  eller fremtidige nye agenter) — designet bør nu eksplicit tage højde for at gøre en undtagelse
  for den nye, godkendte break-glass-vej, i stedet for at blokere den.

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
   **Forudsætning fundet 2026-07-06 (periodisk tjek #65, Claude):** de nuværende 3 kodesteder der
   allerede læser `TIMELAPSE_ENV` (`edge/agent.py`, `headend/main.py`, `headend/siem.py`) kender
   endnu ikke værdien `"rd"` — de bruger stadig den ældre `lab`/`dev`/`development`-terminologi.
   Én af dem (`edge/agent.py`'s legacy-opdaterings-allowlist) vil reelt blokere en gyldig sti hvis
   `TIMELAPSE_ENV=rd` sættes uden samtidig kode-opdatering. Se `RISK_ASSESSMENT_v10.md` R19 for
   detaljer og forslag. Bør rettes FØR `AgentPrincipal`-håndhævelsen bygges oven på variablen, ikke
   efter.

## 7. Styresystem og Cloudflare-arkitektur (afklaret 2026-07-05)

- **OS:** macOS på både `staging` (ældre iMac) og `prod`, samme som `rd` i dag. Historisk startede
  headend på en Raspberry Pi 5 (nu helt udfaset). Fremtidig Linux-understøttelse er ikke udelukket,
  men er bevidst IKKE en del af scope nu — tages op hvis/når det bliver relevant.
- **Cloudflare Tunnel undgås bevidst** (Peters eksplicitte, tidligere aftalte valg) — se §8.

## 8. KORREKTION — Cloudflare Tunnel er IKKE målarkitekturen for prod (og heller ikke "standard 443/80")

Store dele af `GO_LIVE_CHECKLIST_v10.md` §A og `RISK_ASSESSMENT_v10.md`s zone-model (samt
`NGINX_CLOUDFLARE_MIGRATION_LAB_v1.md`) har hidtil antaget at vejen til go-live går via
Cloudflare Tunnel (`cloudflared`, nul åbne indgående porte). **Peter har bekræftet at dette IKKE
er den ønskede prod-arkitektur** — Cloudflare Tunnel skal undgås.

**2. korrektion, samme dag:** Den første version af dette afsnit konkluderede at erstatningen var
"almindelig direkte HTTPS-eksponering på standard port 443" — **det var også forkert.** Peter har
efterfølgende bekræftet at **CrushFTP allerede kører på både staging-iMac'en og prod-Mac Mini'en**
og optager 21, 22, 80 og 443 på begge disse maskiner (til udveksling af kundedata og det
legacy-timelapse-system, TimeLapse Pro skal erstatte). TimeLapse Pro's nginx må derfor ALDRIG
binde til disse porte på staging/prod.

**Den endeligt aftalte arkitektur** (se `PORT_AUDIT_og_WEBSITE_v10.md` §3/§4 for den fulde
begrundelse):
- `backend.timelapse-pro.dk` eksponeres direkte på **port 8443** (ikke 443/80, ikke Cloudflare
  Tunnel) — bekræftet Cloudflare-proxy-kompatibel HTTPS-port (443, 2053, 2083, 2087, 2096, 8443),
  så Peter fortsat kan vælge at lægge Cloudflares gratis WAF/DDoS-beskyttelse (ren DNS-proxy,
  "orange sky", IKKE Tunnel-produktet) foran senere, hvis han ønsker det — det er valgfrit.
- Certifikat udstedes via **DNS-01** (`certbot-dns-cloudflare`), ikke HTTP-01 — rører derfor
  ingen port på maskinen, hverken ved udstedelse eller fornyelse.
- Marketingsitet (`www.timelapse-pro.dk`) hostes **et helt andet sted** end staging-/prod-
  maskinerne (fx Cloudflare Pages) — indgår derfor slet ikke i CrushFTP-portkonflikten.
  `www/index.html`s login-knapper er opdateret til `https://backend.timelapse-pro.dk:8443/`.

**Konsekvens for CA/mTLS-designet (#52):** Model B ("ende-til-ende mTLS til nginx/Headend selv",
`Claude_Intern_CA_mTLS_Design_2026-07-05.md` §6) er fortsat det naturlige valg fremfor Model A
(Cloudflare Access mTLS) — der skal stadig ikke være nogen Cloudflare Tunnel i vejen. Kun
portadressen mTLS/TLS termineres på er ændret (8443, ikke 443). Se opdateret §6/§10 i det
dokument.

**Bemærk:** dette ændrer ikke nødvendigvis noget for `rd`-domænet (`timelapse.froekjaer.dk`),
som er internt/agent-/Peter-vendt, ikke kundevendt, ikke en go-live-blocker og ikke rammet af
CrushFTP (kører ikke der) — `rd` kan fortsat bruge standard 80/443 og evt. Cloudflare (DNS/evt.
proxy) som i dag, uafhængigt af staging-/prod-beslutningen. §A i `GO_LIVE_CHECKLIST_v10.md`,
VPEN-2026-001/002, `RISK_ASSESSMENT_v10.md`s zone-model og hele `PORT_AUDIT_og_WEBSITE_v10.md`
er opdateret til at beskrive den korrekte prod/staging-målarkitektur (se de dokumenter for
detaljer), sammen med `install_headend.sh`, `example-*.conf` og
`INSTALLATION_GUIDE_HEADEND_v1.md`.

Ingen kode er ændret som følge af dette dokument — det er en topologi-/beslutningsafklaring, der
fodrer det videre arbejde med agent-adgangsmodellen og installationsscriptet (se `HANDOVER_LOG.md`
2026-07-05).
