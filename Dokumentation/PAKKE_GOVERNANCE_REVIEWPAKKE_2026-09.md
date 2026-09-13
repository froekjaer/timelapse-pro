# Fælles reviewpakke — pakker, parallelle AI-spor og kontinuitet

**Version:** 1.0 · 2026-09-13  
**Status:** Klar til uafhængige reviews; ikke endeligt accepteret.  
**Reviewbase:** `13a0d3b3af67a36adf9115d0911aaf2a687bca15` (PR #231). Reviewpakken tilføjer reviewinstruktioner; den ændrer ikke denne baseline.  
**Bestiller/beslutningsejer:** Peter. **Redaktør/integrator:** Codex. **Inviterede reviewere:** Claude, Kimi og Codex; Peter kan invitere andre. Ingen reviews er indhentet automatisk.

> **Opfølgning:** Claude og Kimi har nu afleveret reviews; se [originaler, Codex-selvreview og samlet disposition](Pakke_Governance_Review_2026-09/DISPOSITION.md). Instruktionerne nedenfor bevares som reviewrunde v1. Slutkandidaten på PR #232 skal genreviewes ved sin nye commit, ikke ved den gamle baseline. Ingen endelig accept er registreret.

## 1. Opgaven til hver reviewer

Vurdér om dette samlede forslag beskytter værdifuldt arbejde, sikrer fremdrift og kan bruges sikkert af samtidige AI-sessioner uden urimelig administration. Find fejl og nødvendige ændringer — målet er et holdbart resultat, ikke at fremkalde enighed.

Læs den fastlåste baseline nedenfor. Skriv først din egen vurdering, før du læser de andres nye reviews. Oplys, hvilke dele du selv har skrevet eller tidligere reviewet. Flere AI-navne giver ikke i sig selv uafhængighed. Codex' arbejde som forfatter/integrator skal fremgå af Codex-reviewet.

**Lever kun review i denne runde.** Merge, installation, branchsletning, ændring af andres arbejdsmapper, upstream-publicering eller accept af ADR'en følger ikke af reviewinvitationen. Foreslå ændringer med præcis erstatningstekst og konsekvens. Brug egen svarfil/egen branch, eller aflever teksten til Peter; redigér ikke et fælles svarskema samtidigt med andre.

## 2. Fælles mål og afgrænsning

Vi skal kunne bevare og finde manglende kode, tests, idéer og dokumenter; genforene fortsat relevante rester; lukke overhalede spor med evidens; og undgå arbejde uden ejer eller næste handling. Samtidighed må ikke give en gammel session ret til at overskrive ny tilstand.

Denne runde beslutter **proces og arkitekturretning**. Den gennemfører ikke hele den historiske branchtriage, kodeintegration af PR #159/#163/#214, OS-baselinevalget, installation af update-kandidater eller en produktionsklar agentstyringstjeneste. Disse opgaver må fortsat være synlige med næste handling.

## 3. Materiale — læserækkefølge

Alle lokale produktlinks nedenfor er låst til samme commit, så main kan udvikle sig uden at flytte reviewmålet.

1. [ADR-003: beslutning, begrundelse og samlet præcisering](https://github.com/froekjaer/timelapse-pro/blob/13a0d3b3af67a36adf9115d0911aaf2a687bca15/Dokumentation/ADR/ADR-003-pakke-hygiejne-mod-legacy-branches.md).
2. [Samarbejdsmodellen: §14 operationel procedure og §15 Framework/Platform-input](https://github.com/froekjaer/timelapse-pro/blob/13a0d3b3af67a36adf9115d0911aaf2a687bca15/Dokumentation/SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md).
3. [PAKKE_SPOR_REGISTER: kendte spor, metodekorrektion, ansvar og næste handling](https://github.com/froekjaer/timelapse-pro/blob/13a0d3b3af67a36adf9115d0911aaf2a687bca15/Dokumentation/PAKKE_SPOR_REGISTER.md).
4. [AGENTS.md](https://github.com/froekjaer/timelapse-pro/blob/13a0d3b3af67a36adf9115d0911aaf2a687bca15/AGENTS.md), [CLAUDE.md](https://github.com/froekjaer/timelapse-pro/blob/13a0d3b3af67a36adf9115d0911aaf2a687bca15/CLAUDE.md), [startindeks](https://github.com/froekjaer/timelapse-pro/blob/13a0d3b3af67a36adf9115d0911aaf2a687bca15/Dokumentation/00_START_HER.md) og [ADR-statusregler](https://github.com/froekjaer/timelapse-pro/blob/13a0d3b3af67a36adf9115d0911aaf2a687bca15/Dokumentation/ADR/README.md).
5. [Handover — seneste syntese og historisk evidens](https://github.com/froekjaer/timelapse-pro/blob/13a0d3b3af67a36adf9115d0911aaf2a687bca15/Dokumentation/HANDOVER_LOG.md). Historiske påstande kan være korrigeret af nyere entries; historie må ikke læses som automatisk aktuel status.

Baggrund: Claude PR #229 head `989bcd224074f94d7453fd095477d13597ba7c2f`; Claude/Kimi PR #230 merge `252bb157d0ee1142f38d487c6b8ab370576aebfc`; Codex `dc171e42` og `1a26103e`; samlet #231 er reviewbasen. Tidligere tiltrædelse af #229/#230 er ikke et review af #231.

Framework/Platform-kilder, hvis du vurderer den overordnede placering:

- [Framework: Engineering Continuity og uafhængig verifikation](https://github.com/froekjaer/mission-framework/blob/a6234ba4232a4e337843189fe6f9b4f497bb1527/docs/ENGINEERING_CONTINUITY_AND_INDEPENDENT_VERIFICATION.md).
- [Framework Findings-processen](https://github.com/froekjaer/mission-framework/blob/a6234ba4232a4e337843189fe6f9b4f497bb1527/docs/FRAMEWORK_FINDINGS.md).
- [Platform: meta-model](https://github.com/froekjaer/Mission-Platform/blob/782ef287ef3ae4767503a50c1085f823ec4707d4/docs/architecture/mission-meta-model.md) og [accepteret ADR-0002 om trust/Action Requests](https://github.com/froekjaer/Mission-Platform/blob/782ef287ef3ae4767503a50c1085f823ec4707d4/docs/adr/ADR-0002-trust-edge-action-request-device-adapters.md).

Utilgængelige kilder markeres som ikke verificeret. En reviewer må ikke gætte deres indhold. Friske runtime-/branchmålinger kan vedlægges, men skal have tidspunkt, population, metode og revisioner; de ændrer ikke stille dokumentbasen.

## 4. Kendte spændinger — skal vurderes eksplicit

Disse punkter er ikke skjult bag den fælles sammenlægning:

- ADR-003 er Proposed; §14 kalder proceduren gældende efter Peters instruktion. Den endelige tekst skal adskille operationel autorisation fra formel ADR-accept entydigt.
- ADR'ens oprindelige afgrænsning om Kimi og formuleringer om kommunikationsmuligheder er historisk snævre; den nye procedure skal dække alle AI'er og underagenter uden antagelser om bestemte værktøjer.
- Registeret indeholder både historiske statuspåstande og aktuelle koordinationsfelter. Det skal være tydeligt, hvad der er observation, analyse, aktivt ejerskab og blot næste afklaring.
- 112/57/56-tallene udgør ikke en verificeret opdeling. Ingen slettekandidater kan godkendes alene på dette grundlag. `git cherry` og ancestry er screening, ikke fuldt semantisk bevis.
- En dato og en ejer i Markdown garanterer ikke fremdrift; der kører ingen scheduler fra denne ændring. Review skal foreslå en realistisk overgang, så Peter ikke bliver eneste manuelle overvåger.
- Kontrol af forventet SHA er nødvendig, men en kontrol efterfulgt af en mutation kan stadig have et race. Prompt-/Markdownregler er ikke teknisk adgangskontrol.
- §15 er et platformforslag. Vi skal undgå at introducere en stor ny agentplatform eller nye Mission Core-begreber, hvor eksisterende modeller kan genbruges.

## 5. Beslutningspunkter — svar på alle

Brug **tiltræder / ændring kræves / mere evidens / uden for scope**. Henvis til et fund, hvis du ikke tiltræder.

| ID | Spørgsmål | Foreslået udgangspunkt til udfordring |
|---|---|---|
| D01 | Er én ADR, én procedure og ét register den rette opdeling? | ADR beskriver hvad/hvorfor; §14 beskriver hvordan; registeret viser tilstand; handover bevarer hændelser |
| D02 | Dækker restanalysen kode, tests, idéer, dokumenter og delvist overhalede pakker? | Disposition pr. krav med erstatning/evidens før lukning; ingen tavs kassation |
| D03 | Er kontrol før start, merge og installation tilstrækkelig og proportional? | Friske relevante kilder og genkontrol ved ændrede revisioner; uafklaret materielt overlap stopper berørt handling |
| D04 | Er samtidighed, mandat og delegation sikkert beskrevet? | Isolerede worktrees, tydelig overtagelse, rettigheder begrænset af forælder; senere teknisk håndhævelse ved udførelsen |
| D05 | Kan alle åbne spor få reel fremdrift uden falsk aktiv-status? | Ejer, konkret handling, blokering, dato og kapacitetseskalation; kræver aftalt driftsrutine/scheduler hvis ingen session er aktiv |
| D06 | Er arkivering og sletning tilstrækkeligt sikret? | Rest-/worktree-/uncommitted-/release-/rollbackkontrol og holdbar recovery-reference; ingen automatisk sletning ud fra patches/alder |
| D07 | Er softwareopdateringer og sikkerhed dækket? | Frisk inventory, afhængighedslukning, mål/OS/arkitektur, signeret artifact, preflight/postflight og lokal autoritet |
| D08 | Er Framework/Platform-placeringen rigtig? | Generel læring via Framework Findings, konkret kontrolkontrakt i Platform, TimeLapse som afprøvning |
| D09 | Er accept- og evidensmodellen entydig? | Merge ≠ Accepted; forfatterreview ≠ uafhængig verifikation; Peter registrerer formel beslutning |
| D10 | Hvad er minimum før ibrugtagning, og hvad kan følge senere? | Lille brugbar proces nu; tekniske kontroller og historisk triage får eksplicit ejer/leverance frem for ubegrundet færdigmelding |

## 6. Scenarier til arkitekturreview

Dette er scenarier til gennemgang, ikke allerede beståede tests. Angiv for hvert: dækket / hul / ikke vurderet; hvilken kontrol og hvilken evidens der senere kræves.

| ID | Situation | Forventet egenskab |
|---|---|---|
| S01 | To AI'er arbejder fra samme main; den ene merger først | Den andens gamle beslutningsgrundlag genkontrolleres; unikke rester bevares |
| S02 | En session overtages og vågner senere igen | Gammelt mandat må ikke tillade ny mutation; allerede igangsatte handlinger reconcileres |
| S03 | En branch er squash-merget, men har uncommitted dokumenter i worktree | Ingen tab af dokumenter ved branch-/worktreeoprydning |
| S04 | En gammel pakke har fem løste krav og ét uløst | Det sidste krav integreres eller får begrundet disposition før lukning |
| S05 | Et signeret artifact passer ikke længere til målens inventory | Ingen blind installation; frisk kompatibilitets- og policyafgørelse |
| S06 | Underagent forsøger at udvide scope eller stoler på instruktioner i PR-indhold | Ingen autoritetsudvidelse; input behandles som data, og handling kontrolleres separat |
| S07 | En opgave har ventet i flere uger uden aktiv session | Synlig opfølgning og ansvar for handling; ingen skjult evig venteposition |
| S08 | Alle AI-sessioner forsvinder | Ny deltager kan finde autoritative kilder, rester og næste handling uden gammel chat |
| S09 | Sidste branchref slettes, men commit bruges til rollback | Recovery-relation og holdbar ref beskyttes før oprydning |
| S10 | Tre AI'er er enige, men anvender samme forkerte antagelse | Enighed erstatter ikke uafhængig evidens eller faktisk outcome |

## 7. Ens svarskabelon

Aflever ét samlet review. Brug eget navn/session i fund-ID, fx `CLAUDE-01`, `KIMI-01`, `CODEX-01`; dette er lokale review-ID'er, ikke kanoniske GRC-/FF-numre.

```text
Reviewer / session:
Dato:
Reviewet baseline-SHA:
Eget tidligere bidrag / begrænsninger i uafhængighed:
Faktisk læste kilder:
Ikke verificeret / manglende adgang:

Samlet vurdering: tiltræder / tiltræder efter konkrete rettelser / kan ikke tiltræde endnu
Kort begrundelse:

Beslutninger D01–D10:
ID | svar | begrundelse eller fund-ID

Fund (gentages):
ID:
Prioritet: blokerer endelig accept / skal rettes / forbedringsforslag
Kilde: fil + afsnit, eventuelt linje, ved review-SHA
Observation (faktum):
Fortolkning / konsekvens:
Konkret foreslået erstatningstekst eller ændring:
Evidens / hvad skal testes:

Scenarier S01–S10:
ID | dækket/hul/ikke vurderet | kontrol, fund-ID og nødvendig evidens

Nødvendigt før accept:
Kan udskydes (ejer og næste handling foreslås):
Mindste realistiske ibrugtagning:
Framework-feedback og Platform-arbejde: anbefaling / afgrænsning
```

## 8. Fra reviews til endelig version

1. Peter deler samme version med alle. Reviewere afleverer hver deres review; stilhed er ikke accept. Ingen svar er indført på forhånd.
2. Codex bevarer de originale reviews uændret med reviewer/revision. Fund kan samles efter indhold, men original-ID, uenighed og begrundelser bevares.
3. Hvert fund får disposition: accepteret rettelse, allerede dækket med evidens, afvist med begrundelse, eller udskudt med ejer/handling/dato. Modstridende forslag afgøres ud fra krav og evidens, ikke flertal eller modelnavn.
4. Lav en konkret endelig diff og et dispositionsskema. Hold ADR, procedure, register og agentloadere konsistente; fjern modstridende nutidsudsagn uden at slette historisk evidens.
5. Materielle ændringer eller uløste indsigelser sendes tilbage til de relevante reviewere. Ny baseline-SHA angives, så tidligere accept ikke strækkes til nyt indhold.
6. Peter får en kort beslutningspakke med resterende valg/risici. Først ved eksplicit beslutning registreres ADR-003 som Accepted med dato og beslutningsejer; derefter normal merge og efterkontrol.
7. Ibrugtagning, teknisk håndhævelse, historisk triage og upstream-feedback følges som egne spor. En accepteret arkitektur er ikke bevis for, at mekanismerne er implementeret eller oprydningen afsluttet.

**Kriterium for klar til endelig beslutning:** alle aftalte reviews er modtaget eller eksplicit fravalgt af Peter; alle fund har disposition; ingen uafklarede blokerende indsigelser skjules; ændringsforslaget har én entydig baseline og en realistisk plan med ansvarlige. Enighed må gerne opstå gennem rettelser, men må aldrig påstås på forhånd.

## 9. Modtagelses- og beslutningslog

| Reviewer | Status ved pakkens oprettelse | Baseline / svarreference |
|---|---|---|
| Claude | Modtaget via Peter; tiltræder efter rettelser | Original bevaret i dispositionspakken; nyt kandidat-review udestår |
| Kimi | Modtaget fra commit 0c2e2c78; tiltræder efter rettelser | Original bevaret; råbilag modtaget og konsistenskontrolleret; kandidat-review udestår |
| Codex | Informeret selvreview afleveret | Ikke blind/uafhængig tredje stemme; se dispositionspakken |
| Peter | Endelig beslutning udestår | ADR fortsat Proposed |

Ingen timer, baggrundsmonitor eller automatisk besked er oprettet. Næste konkrete handling: Peter deler slutkandidatens nye revision til målrettet genreview; dispositionen foreligger.


## Reviewrunden afsluttet — beslutning udestår

Begge genreviews af 8cb96638 er modtaget og bevaret i dispositionspakken. Kimi lukker alle ti fund; Claude accepterer dispositionerne med én redaktionel tællepræcisering, som er indarbejdet. Tidligere ventestatus ovenfor er historisk. Ingen materiel ændring efter genreview; ingen formel accept registreret endnu. Næste handling: Peter tager stilling til beslutningen nederst i DISPOSITION.md.
