# ADR-003: Pakke-hygiejne — forebyggelse af overhalet/glemt arbejde på tværs af AI-sessioner

- **Status:** Proposed
- **Dato:** 2026-09-13
- **Beslutningstagere:** Peter, Claude, Codex (Kimi inviteres til samme review, jf. §Afgrænsning)
- **Kontekst-referencer:** `HANDOVER_Claude_Codex_arbejdsdeling.md`, `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` (§3 Fælles source of truth, §9 Uenighed og konfliktløsning), `PAKKE_SPOR_REGISTER.md` (nyt, indføres sammen med denne ADR), PR #214, #163, #159.

## Kontekst

Peter rejste en konkret bekymring 2026-09-13: da PR #214 viste sig at være `BEHIND` main, opstod spørgsmålet om hvorvidt en opdatering til branchen risikerer at overskrive eller kritikløst "overhale" arbejde, der reelt stadig mangler at blive integreret. En efterfølgende gennemgang bekræftede at bekymringen er velbegrundet i praksis, ikke kun i teori:

- Repoet har **127 remote branches**, hvoraf kun en håndfuld har en åben PR.
- To Codex-PR'er (**#163** og **#159**) har ligget åbne i 2+ uger uden opfølgning og er nu i reel Git-konflikt med main, fordi main er ændret uafhængigt i de samme filer (bl.a. `edge/agent.py`-refaktorering og `headend/main.py`-modularisering).
- Ved nærmere undersøgelse viste ingen af de to PR'er sig at være overhalet — den funktionalitet de tilføjer (post-restart health-stabilitetsvindue + Headend-sweeper i #163; eksplicitte lokal/UTC-tidsfelter fra capture-API'et i #159) findes ikke andre steder i main. De var blot **glemte**, ikke forkastede.
- Årsagen er strukturel, ikke en enkelt fejl: **flere AI-sessioner (Claude-instanser, Codex, evt. Kimi) arbejder asynkront og taler ikke direkte sammen** (jf. `HANDOVER_Claude_Codex_arbejdsdeling.md` §0: "Vi to assistenter taler ikke direkte sammen"). Uden et fælles, levende overblik over *alle* åbne spor — ikke kun det spor man selv sidder i — er der intet der fanger et glemt branch, før det enten rådner eller (værre) bliver overskrevet af en anden sessions uafhængige, parallelle løsning på samme problem.
- Eksisterende `HANDOVER_LOG.md` løser kontinuitet **inden for** en opgave godt, men er kronologisk og ikke beregnet til at svare på: "hvilke ikke-merged spor findes lige nu, og overlapper noget af det med det jeg er ved at lave?"

## Beslutning

**Før en ny pakke (PR/branch) merges eller en eksisterende pakke opdateres til at følge main, skal den udførende session (menneske eller AI) udføre et pakke-hygiejnetjek:**

1. **Slå op i `PAKKE_SPOR_REGISTER.md`** om der findes andre åbne pakker der rører de samme filer/domæner. Registret er den autoritative liste over kendte åbne spor — ikke `git branch -r` alene, som ikke skelner reelt arbejde fra rådne eksperimenter.
2. **Ved overlap:** afgør om det overlappende spor er
   - **overhalet** (samme problem allerede løst i main på en måde der dækker sporets formål) → dokumentér *hvorfor* i registret med reference til den commit/PR der overtog det, og luk sporet med en kommentar der forklarer beslutningen. Slet aldrig en branch/PR tavst.
   - **stadig gyldigt, men i konflikt** (som #163/#159) → sporet rebases/genforenes mod aktuel main før det merges. Det kasseres ikke, og det merges heller ikke blindt hen over konflikten.
   - **uafklaret** → markeres i registret som `Afventer review` og eskaleres til Peter, hvis ingen AI-session kan afgøre det alene (jf. samarbejdsmodellens §9).
3. **Efter merge af en ny pakke:** opdatér `PAKKE_SPOR_REGISTER.md` — fjern den mergede pakke fra "åbne spor", og tilføj en linje hvis merget hvis noget af det man netop lavede gør et *andet* åbent spor helt eller delvist overflødigt (proaktiv retning, ikke kun reaktiv).
4. **Ved oprettelse af en ny branch/PR:** tilføj den til registret med kort formål, berørte domæner (filstier/moduler) og forfatter (Claude/Codex/Kimi/Peter), så den er synlig for den næste session, før den selv risikerer at rådne.

Dette er en **proces-tjek, ikke en blokerende gate** — det kræver ikke CI-håndhævelse i denne omgang (kan tilføjes senere som et let advarselstjek, analogt til handover-evidenstjekket foreslået i samarbejdsmodellens §13). Det er bindende adfærd for enhver session, menneskelig eller AI, der merger eller opdaterer en pakke.

## Alternativer overvejet

- **Automatisk branch-oprydning (slet gamle branches efter N dage uden aktivitet):** afvist. Ville have slettet #163 og #159, som begge var reelt, uafsluttet arbejde — præcis den skade Peter bad om at undgå. "Gammel" ⇏ "overhalet".
- **Kun stole på `git branch -r --no-merged` + PR-liste:** afvist som eneste mekanisme. Det viser *at* der er ikke-merged branches, men intet om *hvorfor* de stadig er relevante, eller om de overlapper hinanden — det kræver menneske/AI-vurdering, som registret eksisterer for at fastholde.
- **Lade hver AI-session selv huske sine egne åbne spor:** afvist. Modsiger den grundlæggende observation i `HANDOVER_Claude_Codex_arbejdsdeling.md` — sessionerne taler ikke sammen og har ingen delt hukommelse ud over filer i repoet.
- **Realtids cross-AI-kommunikation (Claude ↔ Codex ↔ Kimi):** findes ikke i dag og indføres ikke af denne ADR. Koordination forbliver asynkron via PR-kommentarer, `HANDOVER_LOG.md` og dette register — det er den eneste kanal der faktisk virker på tværs af forskellige AI-værktøjer.

## Konsekvenser

**Positive:**
- Reelt, ufærdigt arbejde (som #163/#159) bliver synligt for enhver session, ikke kun den der oprindeligt startede det.
- Reducerer risikoen for at to sessioner uafhængigt løser samme problem forskelligt, og at den ene version stille overskriver den anden ved merge.
- Giver et konkret sted at dokumentere *hvorfor* noget er vurderet overhalet, i stedet for at det bare forsvinder.

**Negative / omkostninger:**
- Endnu et dokument at vedligeholde. Hvis det ikke opdateres disciplineret, forfalder det til støj ligesom et uvedligeholdt handover-log kunne.
- Kræver at hver session bruger et par minutter på opslag før merge — en lille, men reel friktion.

**Neutrale:**
- Løser ikke i sig selv de 124 branches der endnu ikke er trieret (se `PAKKE_SPOR_REGISTER.md` §Backlog). Denne ADR fastlægger *processen fremadrettet*; den fulde historiske oprydning er et separat, afgrænset arbejde.

## Standardmapping

- **SABSA (kontinuitet/sporbarhed):** registret er et komplementært spor til `HANDOVER_LOG.md` for beslutnings- og arbejdskontinuitet på tværs af sessioner.
- **IEC 62443 / CRA (change management):** forhindrer at sikkerhedsrelevante rettelser (fx #163's update-health-handshake) går tabt eller bliver erstattet af en uddokumenteret parallelløsning uden sporbarhed.
- Ingen direkte GDPR/NIS2-relevans; dette er et udviklingsproces-dokument, ikke en databehandlings- eller driftskontrol.

## Afgrænsning

- Denne ADR beslutter **ikke** hvordan Kimi konkret onboardes til samarbejdsmodellen (separat fra `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md`, som i dag kun navngiver Claude og Codex). Peter har bedt om at samle Claude, Codex og Kimis arbejde til fælles review — denne ADR forudsætter at Kimi følger samme registerpraksis, men formaliserer ikke Kimis rolle i samarbejdsmodellen. Det bør ske som en opdatering af `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` selv, med Peters accept.
- Beslutter **ikke** en CI-håndhævet gate. Kan foreslås som fremtidig ADR-tilføjelse, analogt til handover-evidenstjekket i `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` §13.
- Beslutter **ikke** hvordan de resterende ~124 utrierede branches skal håndteres én for én — kun at nye/kendte spor fremover registreres og tjekkes for overlap. Den historiske oprydning listes som backlog i `PAKKE_SPOR_REGISTER.md`.
