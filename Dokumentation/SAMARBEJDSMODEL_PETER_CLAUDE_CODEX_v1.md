# Samarbejdsmodel for Peter, Claude og Codex

**Version:** 1.0  
**Dato:** 2026-07-16  
**Status:** Proposed - fælles review ønskes

## 1. Formål

Samarbejdet skal gøre TimeLapse Pro sikkert, forståeligt og produktionsklart, samtidig med at arkitekturen kan udvikles til en genbrugelig platform. Dokumentet beskriver, hvordan Peter, Claude og Codex udnytter forskellige perspektiver uden at blande kontekst, gentage arbejde eller gøre Peter til manuel synkroniseringsmekanisme.

## 2. Det samarbejdet allerede giver

- Flere uafhængige reviews opdager forskellige fejlklasser. En implementerende AI og en efterfølgende kritisk reviewer reducerer risikoen for blind spots.
- Fagområder kan kombineres: produktbehov, drift, softwarearkitektur, test, fotografi, SABSA, IEC 62443, ISO 27001, CRA, NIS2, GDPR og FAIR.
- Kontinuitet opnås gennem dokumenteret evidens frem for afhængighed af én chats hukommelse.
- Alternative forslag bliver synlige, før en dyr beslutning gøres bindende.
- Peter beholder produktejerskab og risikoejerskab, mens teknisk kontrol og dokumentation i højere grad automatiseres.

## 3. Fælles source of truth

Prioritetsrækkefølgen er:

1. Verificeret runtime-evidens fra det ægte R&D-miljø.
2. Kode, tests, database-schema og signerede artifacts i Git.
3. Accepterede ADR'er.
4. `00_START_HER.md` og `HANDOVER_LOG.md`.
5. Gældende krav-, risiko- og arkitekturdokumenter.
6. Chatreferater og AI-forklaringer, som aldrig alene er autoritative.

Uoverensstemmelser skjules ikke. De registreres med kilde, evidens, konsekvens, anbefaling og beslutningsejer.

## 4. Roller

### Peter

- Produkt- og risikoejer; fastlægger mål, kundebehov, risikovillighed og endelig accept af dyre eller irreversible arkitekturbeslutninger.
- Skal ikke forventes at kontrollere kode, gentage lange testforløb eller oversætte mellem AI-sessioner.
- Godkender især produktion, eksterne eksponeringer, leverandørtrust, dataretention, væsentlig risikoaccept og accepterede ADR'er.

### Claude og Codex

- Arbejder begge ud fra samme dokumentation og runtime-evidens, uanset hvem der oprindeligt skrev koden.
- Må udfordre hinandens antagelser sagligt og skal skelne mellem dokumenteret faktum, inference og forslag.
- Skal efterlade systemet i en kendt tilstand, køre relevante tests og dokumentere resterende risiko.
- En AI må gerne implementere; den anden bør ved væsentlige ændringer udføre uafhængigt review af kontrakter, sikkerhed og testdækning.

## 5. Handover-kontrakt

Ved væsentligt arbejde opdateres `HANDOVER_LOG.md` med:

- formål og scope;
- ændrede filer, schema og services;
- commit/tag/artifact/update-kandidat;
- udførte tests og konkret resultat;
- runtime-evidens;
- kendte fejl, risiko og næste handling;
- antagelser eller beslutninger, som kræver Peter;
- markering af uncommitted/untracked arbejde.

Handover må ikke blot sige "færdig" eller "testet". Den skal gøre resultatet reproducerbart.

## 6. Arbejdsflow

1. **Orientér:** Læs start/handover, accepterede ADR'er, Git-status og relevant runtime-status.
2. **Afgræns:** Angiv hvilket problem der løses, og hvad der ikke ændres.
3. **Evidens før ændring:** Reproducer fejlen eller etabler baseline.
4. **Implementér additivt:** Bevar data og eksisterende kontrakter, medmindre en godkendt migration kræver andet.
5. **Verificér i lag:** Syntax/type/lint, unit, kontrakt/integration, miljøtest og brugerflow efter risiko.
6. **Review:** Kritiske auth-, update-, backup-, privacy- og arkitekturændringer får uafhængigt review.
7. **Dokumentér og commit:** Kun kendt scope stages; unrelated arbejde bevares.
8. **Deploy gennem det kontrollerede flow:** Ingen direkte produktionsgenveje.

## 7. Hvordan vi skåner Peters kapacitet

- Saml ikke-kritiske spørgsmål i korte beslutningspakker med anbefalet valg, alternativer og konsekvens.
- Afbryd kun straks ved risiko for datatab, sikkerhedshændelse, irreversible handlinger, omkostninger eller behov for risikoejerens accept.
- Brug almindeligt dansk først; tekniske detaljer og evidens kan ligge i dokumentet.
- Vis højst de vigtigste 3-5 aktuelle beslutninger. Resten placeres i backlog med prioritet.
- Bevar sessionkontinuitet i handover, så Peter ikke skal genfortælle historikken.
- Automatisér regressionstest, evidensopsamling, backupverifikation og statusvisning i UI.
- Respektér pauser. Langvarigt, reversibelt arbejde kan fortsætte under den allerede givne R&D-autorisation.

Det er ikke Peters opgave at kompensere for mangelfuld AI-dokumentation eller uklare statusser. Systemet og arbejdsformen skal gøre det let at se: Hvad virker? Hvad er testet? Hvad mangler? Hvad kræver en beslutning?

## 8. Hvordan Peter kan gøre samarbejdet endnu bedre

Peter bidrager allerede med vigtig domæneviden og konkrete observationer fra det ægte miljø. Den mest værdifulde fortsættelse er:

- Beskriv ønsket effekt og prioritet; AI'erne omsætter det til teknisk løsning og test.
- Markér tydeligt, når noget er en fremtidsidé frem for et aktuelt leverancekrav.
- Angiv, når en beslutning har særlig forretnings-, kunde- eller risikobetydning.
- Brug korte acceptbeskeder ved foreslåede beslutningspakker; begrundelse er kun nødvendig, når den ændrer kravene.
- Fortæl, når UI eller forklaring føles utryg eller kryptisk. Det er et produktfund, ikke en brugerfejl.

Peter behøver ikke blive bedre til programmering eller huske alle detaljer. Den vigtigste rolle er at fastholde formål, virkelighed og risikovillighed.

## 9. Uenighed og konfliktløsning

- Ingen AI ændrer en accepteret ADR stiltiende.
- Ved faglig uenighed skriver begge: påstand, evidens, risiko og anbefaling.
- Reversible lavrisikobeslutninger kan afprøves gennem en timeboxed spike og målinger.
- Irreversible, sikkerhedskritiske eller strategiske beslutninger afgøres af Peter efter en kort beslutningspakke.
- Den seneste kode er ikke automatisk den rigtige kode; runtime-evidens og krav vinder.

## 10. Kvalitetsmål for samarbejdet

Vi følger mindst:

- antal genåbnede fejl og regressioner;
- andel kritiske flows med automatiseret miljøtest;
- tid fra fund til reproducerbar evidens;
- antal ændringer uden handover/commit/test;
- restore- og rollback-succesrate;
- antal uafklarede dokumentkonflikter;
- hvor ofte Peter skal gentage kontekst eller udføre unødvendige CLI-trin.

Målet er ikke flest commits eller dokumenter. Målet er et forståeligt system, færre gentagne fejl og lavere belastning på produkt- og risikoejeren.

## 11. Fælles fremtidsvision

TimeLapse Pro kan blive reference-payloaden for en åben, sikker edge-platform til mindre OT-installationer. Platformen kan på sigt levere identitet, policy, sikker opdatering, observability, CMDB/SIEM, backup, JIT-support og kontrollerede conduits, mens leverandører leverer afgrænsede domænepayloads.

Denne vision kræver secure-by-design og et dokumenteret trust-økosystem. Open source reducerer ikke automatisk risiko, og tredjepartsleverandører må ikke få implicit platformtrust. Signering, scope, SBOM/VEX, sårbarhedshåndtering, revocation, tenant-isolation, supportaudit og kundegodkendelse skal være platformegenskaber før et leverandørmarked etableres.

## 12. Næste fælles forbedringer

1. Claude reviewer dette dokument og ADR-001-amendments additivt. ✅ **Udført 2026-07-16 (Claude):** ADR-001 revideret med alle 6 amendments + AI-domænesnit; §13 nedenfor tilføjet.
2. Peter og begge AI'er accepterer en revideret ADR-001 eller dokumenterer uenighed.
3. Der udarbejdes senere en ADR for multi-vendor trust og federation; den implementeres ikke endnu.
4. Handover-formatet gøres maskinvaliderbart i CI, så commits med arkitektur- eller driftsændringer kan advare ved manglende evidens.

## 13. Tekniske samarbejdslærdomme (additivt — Claude, 2026-07-16)

Konkrete ting fra dagens fælles arbejde, der bør være fælles praksis (tilføjet additivt, jf. §4):

- **Verificér mod pinnede afhængigheder, ikke sandkassens.** En AI-sandkasse kan have nyere pakker end produktionens pin. Konkret i dag: `fastapi==0.136.1` (jf. `headend/requirements.txt`) opfører sig anderledes end en sandkasses 0.139.0, hvor `include_router` tabte routes og gav et falsk "vocab/review mangler"-fund. **Regel:** kør verifikation mod `pip install -r`-pinnede versioner + sqlite, ellers er "grønt/rødt" upålideligt. Dette hører under §3's "runtime-evidens skal være reproducerbar".
- **Kend grænsen for hvad en AI-sandkasse må skrive.** En stale `.git/index.lock` (efterladt af en dræbt proces) kunne ikke fjernes fra sandkassen ("Operation not permitted"), og git-symlinks kunne ikke ændres. Selve commit/push (og dermed deploy-trigger) sker på Peters maskine. **Regel:** AI forbereder rene, verificerede ændringer + eksakte copy-paste-kommandoer; den irreversible git-write/deploy er Peters/menneskets skridt (jf. §6.8 og §9).
- **Absolutte symlinks er en latent fælde.** `deploy/*.sh` var committet som absolutte symlinks der kun resolverede på Peters maskine → brød CI (og ville bryde staging/prod). **Regel:** commit kun relative symlinks; CI-shell-tjek skal skippe uresolverbare stier fail-safe uden at maskere reelle syntaksfejl (implementeret 2026-07-15).
- **Handover-evidens bør maskinvalideres (konkretisering af §12.4).** Foreslået CI-tjek: en commit der rører `headend/`, `edge/`, `deploy/` eller `*.sql` uden en tilføjet `HANDOVER_LOG.md`-blok i samme PR → advarsel (ikke hård fejl). Fanger "kode uden evidens" tidligt.
