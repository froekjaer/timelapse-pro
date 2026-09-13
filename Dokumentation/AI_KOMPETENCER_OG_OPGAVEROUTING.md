# AI-kompetencer og dynamisk opgaverouting

Dato: 2026-09-13. Status: **forslag til afprøvning**, ikke implementeret router eller dokumenteret rangliste. Peter har bedt om faste projektdeltagere og budgetbevidst opgavefordeling. Deltagerreglen findes i [samarbejdsmodellen §4](SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md#4-roller); §14 styrer udførelsen. Tidligere genreview af PR #232 godkender ikke automatisk dette nye forslag.

## 1. Anbefaling

Brug først eksisterende abonnementer og én primær udfører pr. opgave. Tilføj uafhængigt review, når risikoen kræver det. Vælg efter dokumenteret kvalitet på vores opgavetype, nødvendige værktøjer og samlet omkostning ved en accepteret leverance. Afprøv API-routing særskilt, hvis målingerne viser en besparelse efter drift og integrationsarbejde.

Et abonnement, en agent-app og en model er forskellige ting. Codex og ChatGPT kan bruge beslægtede modeller; Copilot kan bruge modeller fra flere leverandører. Modelnavn, version, værktøjer og adgang påvirker resultatet. To forskellige logoer garanterer ikke uafhængighed.

## 2. Foreløbig kompetenceafklaring

Startrollerne nedenfor er **forslag**, ikke sammenlignende testresultater. Leverandørdokumentation viser tilgængelige muligheder; den beviser ikke, hvem der er bedst i TimeLapse Pro. Priser, abonnementer og konkret adgang er endnu ikke verificeret for Peters konti.

| Deltager | Foreslået startrolle | Grundlag og vigtig begrænsning |
|---|---|---|
| Codex | Repoanalyse, sammenhængende implementering, tests og integration | Eget arbejde i governancepakken er tilgængeligt, men er ikke uafhængig sammenlignende evidens. Model og indsatsniveau vælges pr. opgave. [Modeller](https://learn.chatgpt.com/docs/models) |
| ChatGPT | Kravafklaring, produktdiskussion, forklaring og anden gennemgang af en beslutning | Skal have relevante kilder og konkret værktøjsadgang. Kan dele modelfamilie med Codex; ikke automatisk uafhængig reviewer. [Modeller](https://learn.chatgpt.com/docs/models) |
| Claude | Implementering samt kritisk arkitektur- og kontraktreview | Projektets bevarede review viser konkrete fund; det er ikke bevis for generel førsteplads. Modelvarianter har forskellige egenskaber. [Modeloversigt](https://platform.claude.com/docs/en/models/overview) |
| Kimi | Afgrænset implementering, branchanalyse og evidenskontrol | Projektets review og korrigerede branchmåling giver konkret erfaring, inklusive behovet for populationskontrol. Versionsvalg skal registreres. [Modelopslag](https://platform.kimi.ai/docs/api/list-models) |
| Z.ai | Pilot på afgrænsede kodeændringer, tests og struktureret review | Fast projektdeltager; ingen sammenlignelig lokal måling er etableret i denne pakke. GLM-version og agentmiljø skal afklares. [Oversigt](https://docs.z.ai/guides/overview/overview) |
| Gemini | Pilot på billeder, multimodalt materiale og større kildesamlinger | Vælg en konkret model med de nødvendige modaliteter; eksisterende billedtagging er ikke bevis for engineering-kompetence. [Modeller](https://ai.google.dev/gemini-api/docs/models) |
| DeepSeek | Pilot på afgrænsede kode- og ræsonneringsopgaver | Aktuel API-dokumentation kunne ikke åbnes i denne undersøgelse. Den officielle V3-kilde er historisk grundlag, ikke aktuel pris-/versionsgaranti. [Officielt repository](https://github.com/deepseek-ai/DeepSeek-V3) |
| Grok | Pilot på kildebaseret research og kritiske modargumenter | Søgning, kildekvalitet og adgang skal verificeres for den konkrete model og klient. [Modeller](https://docs.x.ai/developers/models) |
| GitHub Copilot | IDE-nære ændringer og afgrænsede GitHub-opgaver | Produkt/agentmiljø, ikke én model. Registrér faktisk valgt model; samme bagvedliggende model kan overlappe andre deltagere. [Automatisk modelvalg](https://docs.github.com/en/copilot/concepts/models/auto-model-selection) |

Projektets lokale reviewerfaring findes i [reviewdispositionen](Pakke_Governance_Review_2026-09/DISPOSITION.md) med bevarede originaler. En tiltrædelse er ikke en leverandørattestation.

## 3. Kompetencekort — udfyld pr. konfiguration

Et kort identificerer produkt, leverandør, model/version (eller ukendt), indsatsniveau, klient, værktøjer, adgangsgrænser, dato og evidenscommit. Registrér følgende som **ikke målt**, **bestået med evidens**, eller **utilstrækkeligt til denne opgaveklasse**:

- Forstår krav og finder eksisterende løsninger før ny implementering.
- Finder fejl, retter rodårsagen og bevarer kontrakter.
- Udformer relevante tests og skelner et faktisk testresultat fra en påstand.
- Håndterer arkitektur, sikkerhedsgrænser og konsekvenser for afhængigheder.
- Bevarer kildehenvisninger, usikkerhed og modstridende evidens.
- Arbejder korrekt med nødvendige modaliteter og store kildesæt.
- Følger mandat, samtidighedsregler, datarestriktioner og handover.
- Leverer en anvendelig ændring uden uforholdsmæssig rettetid hos Peter eller andre.

Mål første-gangs-accept, fejl efter review, kritiske oversete fejl, genarbejde, gennemløbstid, forbrug og menneskelig kontroltid. En samlet pointscore må ikke skjule et svigt i sikkerhed eller mandat.

Start med få repræsentative opgaver: lille bugfix, kontraktændring, regressions-test, kildebaseret dokumentation, kritisk review og billedopgave. Sammenlign højst to relevante kandidater pr. kategori i første pilot. Fastlås input og acceptkriterier, undlad at vise facit, og lad en anden bedømme resultatet. Brug ufølsomt materiale eller godkendte, minimerede uddrag. Der er ikke kørt en betalt pilot som del af dette dokument.

## 4. Routingbeslutningen

1. **Adgangskrav:** Er databehandling tilladt, værktøjer tilstrækkelige, mandat klart og opgaven inden for konfigurationens grænser? Ellers er kandidaten udelukket.
2. **Kvalitetskrav:** Brug lokal evidens for samme opgavetype. En uprøvet kandidat får en afgrænset pilot, ikke en kritisk produktionsopgave alene.
3. **Økonomi:** Blandt egnede kandidater vælges laveste forventede samlede omkostning inklusive review, fejlretning og gentagelser. Allerede betalt abonnement kan have lav ekstra kontantpris, men kvoter er stadig begrænsede. Abonnementer må ikke antages at inkludere API-kald.
4. **Udførelse:** Én tydelig ejer; leverance og acceptkriterier før start. Standardforslag: højst ét rettelsesforsøg før eskalering eller stop. Ingen ubegrænset kæde af dyrere modeller.
5. **Review:** Auth, opdateringer, migration, backup/recovery og andre væsentlige tillidsgrænser kræver uafhængig kontrol. Forskellig kontekst og metode tæller; produktnavnet alene gør ikke.
6. **Læring:** Gem resultat og faktisk forbrug mod konfigurationen. Genafprøv ved ny model, værktøjsændring, prisændring eller regression. Brug seneste relevante evidens, ikke et evigt brandhierarki.

Budgetrammen skal angive abonnementer, ekstra API-loft, loft pr. opgave og et samlet håndhævet loft ved parallelle opgaver. Ukendt budget giver ikke lov til nyt forbrug. En routers prispræference er ikke et økonomisk stop. Ved utilstrækkeligt budget returneres en konkret begrænsning; kvalitets- eller sikkerhedskrav sænkes ikke tavst.

## 5. Eksisterende routingmuligheder

| Mulighed | Hvad den kan bruges til | Begrænsning for os |
|---|---|---|
| [OpenRouter Auto Router](https://openrouter.ai/docs/guides/routing/routers/auto-router) | Automatisk valg mellem tilladte API-modeller, med model- og prispræferencer | Ekstra databehandler/gateway og API-forbrug; cost tier er ikke et hårdt budgetloft. Kræver vores evaluering. |
| [LiteLLM Router](https://docs.litellm.ai/docs/routing) | Fordeling mellem modeldeployments efter bl.a. belastning, latency og pris | Ikke i sig selv bevisbaseret valg af bedste projektagent; kræver policy, måling og drift. |
| [RouteLLM](https://github.com/lm-sys/RouteLLM) | Ramme til at evaluere og lære routing mellem stærkere og billigere modeller | Kræver kalibrering på relevante opgaver; erstatter ikke mandat og agentkoordinering. |
| [Copilot Auto](https://docs.github.com/en/copilot/concepts/models/auto-model-selection) | Automatisk modelvalg inden for Copilots understøttede produkter og abonnement | Fordeler ikke arbejde til alle vores separate AI-apps. Faktisk modelvalg skal kunne spores. |

**Anbefalet rækkefølge:** manuel, dokumenteret opgavefordeling → lille kontrolleret måling → eventuel API-router. En modelrouter vælger en model til et kald; en projektkoordinator håndterer opgaver, værktøjer, ejerskab, review og recovery. De er forskellige funktioner. Ingen af disse løsninger er installeret eller tilkoblet Headend her.

## 6. Mission Framework og Mission Platform

Framework har allerede principper, vi bør genbruge:

- [Trust bootstrap og evidence maturity](https://github.com/froekjaer/mission-framework/blob/a6234ba4232a4e337843189fe6f9b4f497bb1527/docs/operational/TRUST-BOOTSTRAP-CREDIBILITY-ONBOARDING-EVIDENCE-MATURITY.md): tillid opbygges gennem evidens. En foreslået rolle er ikke en reproduceret kompetence.
- [Uafhængig verifikation](https://github.com/froekjaer/mission-framework/blob/a6234ba4232a4e337843189fe6f9b4f497bb1527/docs/ENGINEERING_CONTINUITY_AND_INDEPENDENT_VERIFICATION.md): kontinuitet og kontrol skal overleve den enkelte session.
- [MIAR-reviewskabelon](https://github.com/froekjaer/mission-framework/blob/a6234ba4232a4e337843189fe6f9b4f497bb1527/reviews/MIAR/RESPONSE-TEMPLATE.md): identificér model, kontekst, evidens og uafhængighed.

**Forslag til Framework-feedback:** eksplicit princip om evidensbaseret, genvurderbar kompetence og budget under ufravigelige mandat-/datagrænser. Før et nyt Framework Finding oprettes, skal eksisterende findings kontrolleres for overlap. Der er ikke oprettet et nyt kanonisk ID her.

**Forslag til Platform:** kompetencekort med gyldighed/proveniens, evalueringsresultater, budgetreservation på tværs af samtidige opgaver, routingbegrundelse, mandatkontrol og sporbar eskalering. Integrér med den eksisterende [mission-metamodel](https://github.com/froekjaer/Mission-Platform/blob/782ef287ef3ae4767503a50c1085f823ec4707d4/docs/architecture/mission-meta-model.md), frem for en konkurrerende Mission Core. En router må foreslå en udfører, men må ikke give sig selv adgang eller udvide mandatet. Dette er et designforslag, ikke en påstand om eksisterende funktionalitet.

## 7. Næste afklaring og ansvar

Codex har udarbejdet forslaget efter Peters instruktion. Peter afklarer eksisterende abonnementer og ekstra forbrugsramme; derefter kan en konkret lille pilot prissættes og fordeles. Review af denne udvidelse udestår. Aktive leverancer føres i det eksisterende pakkesporregister, ikke i en ny konkurrerende backlog. Ingen automatisk genmåling eller scheduler er oprettet.
