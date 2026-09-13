# ADR-003: Pakke-hygiejne — forebyggelse af overhalet/glemt arbejde på tværs af AI-sessioner

- **Status:** Accepted
- **Accept:** Peter, 2026-09-13, efter Claude/Kimi-genreviews og instruktion om at afslutte det reviewede arbejde. Omfatter ADR-003 og §14; ikke implementering af de åbne opfølgningsspor.
- **Dato:** 2026-09-13
- **Beslutningsejer:** Peter. Reviewbidrag: Claude, Kimi og Codex (se bevarede reviews/disposition).
- **Historisk review af #230, selvrapporteret identitet; ikke accept af senere syntese:** Kimi 2026-09-13 — **tiltræder ADR'en uden ændringskrav**. Verificerede kontekst-påstandene mod repoet (127 branches, #163/#159-conflicts) og bidrog med den målte branch-klassificering i `PAKKE_SPOR_REGISTER.md` §Backlog. Én metode-præcisering: sweeps skal bruge patch-ækvivalens (`git cherry`), da `git log main..<branch>` fejlagtigt viser squash-mergede branches som ikke-mergede.
- **Kontekst-referencer:** `HANDOVER_Claude_Codex_arbejdsdeling.md`, `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` (§3 Fælles source of truth, §9 Uenighed og konfliktløsning), `PAKKE_SPOR_REGISTER.md` (nyt, indføres sammen med denne ADR), PR #214, #163, #159.

## Kontekst

Peter rejste en konkret bekymring 2026-09-13: da PR #214 viste sig at være `BEHIND` main, opstod spørgsmålet om hvorvidt en opdatering til branchen risikerer at overskrive eller kritikløst "overhale" arbejde, der reelt stadig mangler at blive integreret. En efterfølgende gennemgang bekræftede at bekymringen er velbegrundet i praksis, ikke kun i teori:

- Repoet har **127 remote branches**, hvoraf kun en håndfuld har en åben PR.
- To Codex-PR'er (**#163** og **#159**) har ligget åbne i 2+ uger uden opfølgning og er nu i reel Git-konflikt med main, fordi main er ændret uafhængigt i de samme filer (bl.a. `edge/agent.py`-refaktorering og `headend/main.py`-modularisering).
- Claudes foreløbige strengsøgning gav indikation af, at de to PR'er ikke var fuldt overhalet — den funktionalitet de tilføjer (post-restart health-stabilitetsvindue + Headend-sweeper i #163; eksplicitte lokal/UTC-tidsfelter fra capture-API'et i #159) blev ikke fundet ved den beskrevne søgning. Det er screening fra samme forfatter, ikke en fuld uafhængig semantisk gennemgang; genverifikation udestår før integration.
- Årsagen er strukturel, ikke en enkelt fejl: **flere AI-sessioner (Claude-instanser, Codex, evt. Kimi) arbejder asynkront og taler ikke direkte sammen** (jf. `HANDOVER_Claude_Codex_arbejdsdeling.md` §0: "Vi to assistenter taler ikke direkte sammen"). Uden et fælles, levende overblik over *alle* åbne spor — ikke kun det spor man selv sidder i — er der intet der fanger et glemt branch, før det enten rådner eller (værre) bliver overskrevet af en anden sessions uafhængige, parallelle løsning på samme problem.
- Eksisterende `HANDOVER_LOG.md` løser kontinuitet **inden for** en opgave godt, men er kronologisk og ikke beregnet til at svare på: "hvilke ikke-merged spor findes lige nu, og overlapper noget af det med det jeg er ved at lave?"

## Beslutning — hvad og hvorfor

Beslutningen fastlægger bevaring af relevant restindhold, synlig koordinering før ændringer og dokumenteret disposition før oprydning. Det skal forebygge tab af kode, tests, idéer og beslutningshistorik på tværs af parallelle sessioner. Registret giver overblik; handover bevarer hændelser; faktiske Git/GRC/CMDB-kilder forbliver autoritative for deres respektive tilstande.

Den eneste operative procedurespecifikation er [samarbejdsmodellen §14](../SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md#14-bindende-regel-for-pakker-spor-og-reconciliation). Denne ADR gentager ikke dens trin. Proceduren er accepteret af Peter sammen med denne ADR 2026-09-13. Teknisk CI-/serverhåndhævelse følger ikke af dokumentet.

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

Reglen er leverandørneutral og gælder mennesker, alle AI-sessioner og underagenter. Teknisk håndhævelse, historisk branchtriage og Framework/Platform-udvidelser er separate leverancer; dokumentet påstår ikke at de er udført. Samarbejdskanaler afhænger af faktisk autoriseret tooling; ingen bestemt AI-kommunikationsmulighed eller -begrænsning antages universel.

## Samlet præcisering — Claude, Kimi og Codex, 2026-09-13

Claude leverer ADR/register og konkrete konfliktanalyser; Kimi bidrager med historisk sweep og patch-ækvivalens som supplerende metode; Codex supplerer med restdisposition, samtidighed, driftskandidater, fremdrift og Framework/Platform-feedback. Kilder: PR #229 head `989bcd22`, PR #230 merge `252bb157`, Codex `dc171e42`/`1a26103e`. Denne syntese er udført af Codex; den er ikke en påstand om at alle tre har reviewet slutteksten.

Den konkrete procedure findes ét sted: [samarbejdsmodellen §14](../SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md#14-bindende-regel-for-pakker-spor-og-reconciliation). Den omfatter alle AI'er og underagenter, også ved start og installation, samt register/ejer/opfølgning, frisk main/head-kontrol og kontrolleret overtagelse. Uafklaret væsentligt overlap stopper den berørte mutation; ingen automatisk CI-lås er indført.

`git cherry` sammenligner individuelle patch-ID'er og er et screeningsværktøj. Flere commits squash-merget til én kan stadig fremstå unikke. Hverken 0 unikke commits, patch-ækvivalens, alder eller en lukket PR er alene slettebevis. Restindhold, worktrees, uncommitted/untracked materiale, aktive sessioner, release-/rollbackreferencer og holdbar recovery skal være afklaret. Delvist overhalede spor gennemgås pr. krav/idé; beslutningshistorik bevares.

Registerets ældre tal er historiske observationer og ikke autoriseret slettekø. Se korrektion og metodebegrænsning dér. Framework/Platform-input i samarbejdsmodellens §15 er foreslået videre arbejde, ikke en vedtaget udvidelse af nogen af de to repositories.
