# TimeLapse Pro — Architecture Governance v1

**Status:** Proposed  
**Dokumenttype:** Normativt governance- og målarkitekturdokument  
**Version:** 1.0  
**Dato:** 2026-07-31  
**Anvendelse:** TimeLapse Pro, Mission Timelapse og fremtidige Mission Framework-baserede løsninger

---

## 1. Formål

Dette dokument fastlægger, hvordan arkitekturen for TimeLapse Pro styres, udvikles, reviews, accepteres, implementeres, verificeres og udfases.

Formålet er at sikre, at væsentlige ændringer sker gennem dokumenterede, reviewbare og evidensbaserede beslutninger — ikke gennem tilfældige kodeændringer, implicitte antagelser eller viden, der alene findes i en chatsession eller hos én udvikler.

Architecture Governance skal:

- beskytte produktets langsigtede formål og sikkerhedsegenskaber
- skabe tydeligt ansvar for beslutninger
- gøre relationen mellem policy, kontrakter, implementering og drift sporbar
- forhindre at sikkerhed og modularitet gradvist udhules
- understøtte kontrolleret innovation
- gøre operationelle erfaringer anvendelige som input til Mission Framework
- sikre, at både mennesker og AI-assistenter arbejder efter samme styrende grundlag

Governance er ikke et mål i sig selv. Governance er en mekanisme til at forbedre beslutningskvalitet, reducere risiko og bevare systemets sammenhæng over tid.

---

## 2. Scope

Dokumentet gælder for væsentlige ændringer i:

- produktpolitik og designprincipper
- platform/payload-arkitektur
- sikkerhedsarkitektur
- data- og evidenshåndtering
- identitet, autentifikation og autorisation
- Local Service Gateway og lokal serviceadgang
- hardware abstraction og device capabilities
- API'er og integrationskontrakter
- update-, release- og rollbackmekanismer
- observability, audit og hændelseshåndtering
- AI-funktioner og AI-governance
- projektlivscyklus og disposition af data
- Mission Framework-relaterede kontrakter og findings

Dokumentet gælder ikke kun for kode. Det gælder også for dokumentation, konfiguration, driftsprocedurer, hardwareprofiler, sikkerhedskontroller og organisatoriske beslutninger, når disse påvirker systemets arkitektur eller risikoprofil.

---

## 3. Forhold til øvrige styrende dokumenter

Architecture Governance skal læses sammen med følgende dokumenttyper:

### 3.1 Core Design Principles

`TimeLapse_Core_Design_Principles_v1.md` beskriver produktets normative principper og målarkitekturens grundlæggende egenskaber.

Det dokument beskriver primært:

- hvorfor systemet eksisterer
- hvilke egenskaber der skal beskyttes
- hvilke handlinger der er tilladte eller forbudte
- hvilken langsigtet retning arkitekturen skal følge

Architecture Governance beskriver, hvordan disse principper omsættes til beslutninger og ændringer.

### 3.2 Architecture Decision Records

ADR'er beskriver konkrete arkitekturbeslutninger, deres kontekst, alternativer, konsekvenser og status.

Eksempler:

- ADR-001: Platform/Payload-snit
- ADR-002: Kontraktsæt v1
- ADR-003: Reserveret til pakkeformat, signering, isolation og control/data-plane-transport
- foreslået ADR: Controlled Local Service Access
- foreslået ADR: Evidence Retention and Explicit Disposition

Core Design Principles er policy-laget. ADR'erne er de konkrete beslutninger. Kontrakter og runtime-kontroller er de maskin-håndhævede grænser.

### 3.3 SABSA Security Architecture

SABSA-arkitekturen beskriver, hvordan forretningsattributter, risici, trust boundaries og sikkerhedskontroller omsættes til en sammenhængende sikkerhedsarkitektur.

Architecture Governance sikrer, at sikkerhedsarkitekturen:

- indgår tidligt i beslutningsprocessen
- bliver reviewet sammen med funktionelle ændringer
- ikke reduceres til efterfølgende compliance-kontrol
- kan spores til konkrete risici og business attributes

### 3.4 Mission Framework

TimeLapse Pro fungerer som referenceimplementering og læringsplatform for Mission Framework.

Erfaringer fra TimeLapse må ikke automatisk ophøjes til generelle framework-principper. De skal først dokumenteres som operationelle observationer, gennemgås kritisk og modnes som Framework Findings.

---

## 4. Governance-filosofi

### 4.1 Arkitektur er et forretningsaktiv

Arkitektur er ikke alene tekniske diagrammer. Den beskytter:

- kontinuitet
- kundetillid
- evidensværdi
- sikkerhed
- vedligeholdbarhed
- regulatorisk robusthed
- mulighed for senere udskiftning af teknologi

Arkitekturen skal derfor styres med samme alvor som andre langsigtede aktiver.

### 4.2 Beslutninger før implementering

Væsentlige ændringer skal starte med en tydelig beslutning eller et reviewbart forslag.

Normal rækkefølge:

```text
Behov eller observation
        ↓
Analyse og risikovurdering
        ↓
Princip, ADR eller specifikation
        ↓
Review og accept
        ↓
Implementering
        ↓
Verifikation
        ↓
Operationel erfaring
```

Mindre, reversible implementeringsdetaljer kan besluttes i kode-review. Ændringer med bred, langsigtet eller sikkerhedsmæssig konsekvens kræver arkitekturbehandling.

### 4.3 Evidens frem for autoritet

En beslutning skal vurderes på:

- dokumenteret behov
- observerede forhold
- konsekvenser
- risici
- alternativer
- testbarhed
- reversibilitet
- driftsmæssig evidens

Den skal ikke vurderes ud fra, hvem eller hvilken AI der foreslog den.

### 4.4 Evolution frem for ukontrolleret revolution

TimeLapse Pro er et kørende system. Målarkitekturen skal normalt realiseres gennem kontrollerede, additive og verificerbare inkrementer.

Store omskrivninger kræver særskilt begrundelse, migrationsplan, rollback og evidens for, at risikoen er acceptabel.

### 4.5 Governance skal muliggøre innovation

Governance må ikke blive et generelt krav om lange dokumenter for små ændringer.

Kontrolniveauet skal stå i forhold til:

- konsekvens
- irreversibilitet
- sikkerhedsrisiko
- påvirket scope
- regulatorisk betydning
- antal systemer og brugere
- fremtidig binding

---

## 5. Styrende governance-principper

### Princip 1 — Arkitektur skal være tilsigtet

Væsentlige systemegenskaber må ikke opstå tilfældigt gennem kumulative lokale ændringer.

### Princip 2 — Væsentlige beslutninger skal dokumenteres

Beslutninger med langsigtet, tværgående eller sikkerhedsmæssig effekt skal kunne findes og forstås efterfølgende.

### Princip 3 — Policy går forud for mekanisme

Systemets ønskede adfærd skal defineres, før den konkrete tekniske mekanisme vælges.

Eksempel:

- Policy: Projekt-evidens må ikke slettes automatisk.
- Kontrakt: Data klassificeres med en eksplicit retention class.
- Mekanisme: Runtime afviser destruktive operationer uden korrekt capability og autorisation.

### Princip 4 — Interfaces er kontrakter

Platform, payload, services, HAL og eksterne integrationer skal kommunikere gennem versionerede, testbare kontrakter.

### Princip 5 — Sikkerhed er integreret

Sikkerhedsreview er en del af arkitektur- og implementeringsreview, ikke en separat efterkontrol.

### Princip 6 — Fail-closed ved uklar autoritet

Hvis identitet, rolle, policy, capability eller dataklassifikation ikke kan valideres, skal privilegeret eller destruktiv handling afvises.

### Princip 7 — Reversibilitet foretrækkes

Hvor det er praktisk muligt, skal ændringer kunne tilbagerulles, migreres eller deaktiveres.

### Princip 8 — Dokumentation og kode skal kunne spores

Normative dokumenter, ADR'er, specifikationer, tests og implementering skal pege på hinanden, hvor relationen er væsentlig.

### Princip 9 — AI rådgiver; mennesker er ansvarlige

AI-assistenter kan analysere, foreslå, reviewe og formulere. De kan ikke alene acceptere risiko, ændre produktpolitik eller godkende produktion.

### Princip 10 — Operationel erfaring skal tilbageføres

Verificerede erfaringer fra drift skal kunne ændre ADR'er, målarkitektur og Mission Framework gennem en kontrolleret proces.

---

## 6. Arkitekturhierarki

Følgende hierarki anvendes:

```text
Mission og forretningsmål
        ↓
Core Design Principles
        ↓
Architecture Governance
        ↓
SABSA Security Architecture
        ↓
Architecture Decision Records
        ↓
Målarkitektur og domænearkitekturer
        ↓
Tekniske specifikationer og kontrakter
        ↓
Implementering
        ↓
Tests og evidens
        ↓
Operationel drift
        ↓
Operational Learning / Framework Findings
```

Hierarkiet betyder ikke, at arbejdet altid er lineært. Implementering kan afsløre forhold, der kræver ændring af en specifikation eller ADR. Sådanne ændringer skal føres tilbage gennem dokumenthierarkiet og ikke skjules som lokale kodeafvigelser.

---

## 7. Dokumenttyper og normativ styrke

### 7.1 Normative dokumenter

Definerer bindende eller foreslåede regler og mål.

Eksempler:

- Core Design Principles
- Architecture Governance
- accepterede ADR'er
- sikkerhedspolitikker
- godkendte kontraktspecifikationer

Normative udsagn bør anvende tydelige ord som:

- SHALL / skal
- SHALL NOT / må ikke
- SHOULD / bør
- MAY / kan

### 7.2 Målarkitektur

Beskriver den ønskede fremtidige arkitektur. Den kan være Proposed, selv om implementeringen endnu ikke følger den fuldt ud.

As-is og target state skal holdes tydeligt adskilt.

### 7.3 Reference- og analysedokumenter

Beskriver analyser, muligheder, assessmentfund eller baggrund. De er ikke automatisk bindende.

### 7.4 Operationelle dokumenter

Runbooks, installationsvejledninger, recovery-procedurer og driftsinstruktioner beskriver den faktiske, anvendelige procedure.

### 7.5 Genererede dokumenter

Rapporter genereret fra databaser, tests, GRC-registre eller scripts skal tydeligt angive kilde, tidspunkt og om de er autoritative eller snapshots.

### 7.6 Historiske og deprecated dokumenter

Forældede dokumenter bevares som historik, men må ikke fremstå som aktuelle beslutningskilder.

---

## 8. Architecture Lifecycle

Arkitekturartefakter kan have følgende tilstande:

### 8.1 Draft

Et tidligt arbejdsdokument. Ikke klar til formelt review.

### 8.2 Proposed

Et komplet forslag, der kan reviews. Det beskriver en ønsket beslutning eller måltilstand, men er endnu ikke bindende.

### 8.3 In Review

Forslaget gennemgår et eller flere relevante reviews.

### 8.4 Accepted

Den ansvarlige menneskelige authority har accepteret beslutningen.

Accepted betyder ikke nødvendigvis, at beslutningen allerede er implementeret.

### 8.5 Implemented

Den relevante implementering er gennemført, men kan stadig mangle fuld operationel verifikation.

### 8.6 Verified

Implementeringen er testet mod beslutningens acceptkriterier, og nødvendig evidens findes.

### 8.7 Operational

Løsningen er i anvendelse under den tiltænkte driftsmodel.

### 8.8 Deprecated

Artefaktet eller beslutningen bør ikke længere anvendes til nye løsninger, men eksisterende anvendelse kan fortsætte midlertidigt.

### 8.9 Superseded

En nyere beslutning erstatter den tidligere. Den tidligere ADR bevares som historik og peger på afløseren.

### 8.10 Retired

Beslutningen eller komponenten anvendes ikke længere.

---

## 9. Hvornår kræves arkitekturbehandling?

En ADR eller tilsvarende behandling kræves normalt, når en ændring:

- ændrer en trust boundary
- ændrer platform/payload-snittet
- introducerer en ny ekstern afhængighed eller leverandørbinding
- ændrer dataejerskab, retention eller disposition
- ændrer autentifikation, autorisation eller privilegier
- ændrer update-, signerings- eller rollbackmodellen
- introducerer en ny lokal eller remote servicekanal
- ændrer et offentligt eller internt kontraktinterface
- ændrer hardware abstraction eller capability-modellen
- påvirker audit, evidens eller integritet
- ændrer en accepteret ADR
- skaber væsentlig irreversibilitet
- har tværgående betydning for flere moduler eller produkter
- kan blive et generelt princip i Mission Framework

En ADR er normalt ikke nødvendig for:

- intern refaktorering uden kontraktændring
- mindre UI-justeringer
- fejlrettelser, der genskaber allerede besluttet adfærd
- dependency-opdateringer uden væsentlig arkitektur- eller risikoeffekt

Ved tvivl dokumenteres beslutningen mindst som et kort designnotat eller PR-afsnit med rationale.

---

## 10. ADR Governance

### 10.1 Indhold

En ADR skal som minimum indeholde:

- titel og ID
- status
- dato
- kontekst og problem
- beslutning
- alternativer
- konsekvenser
- sikkerheds- og driftsmæssig betydning
- migrations- eller implementeringsvej
- verifikationskriterier
- relationer til øvrige ADR'er og normative dokumenter

### 10.2 Ejerskab

Hver ADR skal have en tydelig beslutningsauthority. For TimeLapse Pro er den endelige produkt- og risikobeslutning menneskelig.

### 10.3 Scope

En ADR bør beskrive én sammenhængende beslutning. Hvis dokumentet forsøger at eje både policy, kontrakter, runtime isolation, pakkeformat og transport, skal det vurderes, om scope bør deles.

ADR-002/ADR-003-afgrænsningen er et eksempel:

- ADR-002 ejer kontrakterne
- ADR-003 er reserveret til pakkeformat, signering, isolation og control/data-plane-transport
- Core Design Principles og policy-ADR'er ejer de styrende regler

### 10.4 Ændringer

En accepteret ADR redigeres ikke, så dens oprindelige beslutningshistorik skjules.

Ved væsentlig ændring skal der normalt:

- oprettes en ny ADR, der superseder den gamle, eller
- tilføjes en tydeligt dateret amendment med begrundelse

### 10.5 Accept

En ADR kan blive Accepted, når:

- problemet er tydeligt
- alternativer er vurderet
- konsekvenser er beskrevet
- relevante reviews er gennemført
- konflikter med øvrige beslutninger er behandlet
- Product Owner eller udpeget authority har accepteret

---

## 11. Roller og ansvar

Roller er funktioner og behøver ikke være forskellige personer.

### 11.1 Business Authority / Product Owner

Ansvar:

- produktets formål og prioritering
- accept af væsentlig risiko
- endelig accept af normative produktprincipper
- beslutning om trade-offs mellem værdi, risiko og omkostning

### 11.2 Architecture Authority

Ansvar:

- tværgående sammenhæng
- modularitet og kontrakter
- relationen mellem as-is og target state
- ADR-kvalitet
- teknologisk udskiftelighed
- langsigtet vedligeholdbarhed

### 11.3 Security Authority

Ansvar:

- trust boundaries
- trusselsmodel
- SABSA business attributes
- identitet, adgang og audit
- standard- og regulatorisk alignment
- behandling af sikkerhedsafvigelser

### 11.4 Implementation Authority

Ansvar:

- realistisk implementeringsvej
- kodekvalitet
- tests
- CI
- migration og rollback
- korrekt sammenhæng mellem dokumentation og repository

### 11.5 Operational Authority

Ansvar:

- driftsrealitet
- runbooks
- observability
- recovery
- serviceability
- dokumentation af operationel evidens

### 11.6 Reviewers

Reviewers skal udfordre antagelser, inkonsistens, skjult scope, manglende evidens og urealistiske implementeringsplaner.

Et review er ikke en formalitet eller en generel kvalitetsstempling.

### 11.7 AI Review Support

AI-assistenter kan udfylde forskellige støttefunktioner, eksempelvis:

- repository- og implementeringsreview
- dokumentkonsistens
- arkitektur- og sikkerhedsanalyse
- udkast til ADR'er og specifikationer
- test- og evidensanalyse

AI-output er et reviewinput, ikke en selvstændig authority.

---

## 12. Reviewmodel

### 12.1 Business Review

Vurderer:

- hvilket problem der løses
- forventet værdi
- berørte aktører
- konsekvenser ved fejl
- om løsningen er proportional

### 12.2 Architecture Review

Vurderer:

- sammenhæng med Core Design Principles
- platform/payload-snit
- kontrakter og ejerskab
- teknologibinding
- migrerbarhed
- testbarhed
- failure behaviour

### 12.3 Security Review

Vurderer:

- aktiver og trusler
- trust boundaries
- identitet og autorisation
- dataflow og dataklassifikation
- audit og evidens
- misuse cases
- relevante krav fra SABSA, ISO/IEC 27001, IEC 62443, CRA, GDPR, NIS2 og AI Act

### 12.4 Repository Review

Vurderer:

- korrekt placering
- dokumenthierarki
- links og krydsreferencer
- ADR-register
- onboarding
- handover
- versions- og statusmarkering

### 12.5 Implementation Review

Vurderer:

- kontraktoverholdelse
- sikker server-side enforcement
- tests og negative testcases
- rollback
- logging og observability
- secrets og hardkodede værdier
- performance og failure recovery

### 12.6 Operational Review

Vurderer efter implementering:

- faktisk anvendelighed
- driftsfejl
- servicehistorik
- menneskelige arbejdsgange
- data- og auditkvalitet
- om antagelserne i ADR'en holdt

---

## 13. Definition of Accepted

Et dokument eller en beslutning er ikke Accepted alene fordi:

- det er skrevet overbevisende
- CI er grøn
- en AI-assistent anbefaler det
- implementeringen allerede er påbegyndt
- ingen har kommenteret inden for en bestemt periode

Accept kræver:

- kendt scope
- tydelig status
- relevante krydsreferencer
- behandlede konflikter
- dokumenterede konsekvenser
- passende review
- eksplicit menneskelig beslutning

---

## 14. Definition of Implemented og Verified

### Implemented

En beslutning kan markeres Implemented, når:

- nødvendig kode, konfiguration og dokumentation er til stede
- migrationsvej er gennemført
- relevante komponenter anvender løsningen
- kendte afvigelser er dokumenteret

### Verified

En beslutning kan markeres Verified, når:

- acceptkriterier er testet
- negative og failure cases er testet
- sikkerhedskontroller er verificeret
- observability og audit fungerer
- rollback eller recovery er afprøvet, hvor relevant
- evidens kan findes og reproduceres

CI-grøn er nødvendig, men ikke altid tilstrækkelig. Hardware-, integrations- og driftsafhængige beslutninger kan kræve live-verifikation.

---

## 15. Repository Governance

### 15.1 Branches

Væsentlige arkitektur- og dokumentationsændringer udvikles på en separat branch.

Branches skal have tydeligt scope og må ikke blande uvedkommende runtimeændringer ind i et dokumentationsreview.

### 15.2 Pull Requests

En PR skal beskrive:

- hvad der ændres
- hvorfor
- dokumentets eller kodens status
- påvirkning
- risici
- tests og verifikation
- åbne beslutninger

Normative dokumenter bør normalt starte som draft PR og Proposed.

### 15.3 Merge

Merge-rækkefølgen skal minimere konflikt og sikre, at policy og kontrakter lander før afhængig implementering, hvor det er praktisk muligt.

En typisk rækkefølge er:

```text
Normativ beslutning
        ↓
Kontrakt/specifikation
        ↓
Assessment eller plan
        ↓
Implementering
        ↓
Live-verifikation
```

### 15.4 Handover

Væsentligt arbejde skal registreres i `Dokumentation/HANDOVER_LOG.md` med:

- branch
- commit
- status
- hvad der er ændret
- åbne beslutninger
- næste ansvarlige handling
- kendte merge-konflikter

### 15.5 Dokumentindeks

Nye styrende dokumenter skal linkes fra relevante onboarding-, oversigts- og arkitekturdokumenter, når de nærmer sig accept.

---

## 16. Sikkerheds- og compliance-governance

Standarder anvendes risikobaseret og gennem sporbarhed — ikke som isolerede checklister.

En væsentlig arkitekturbeslutning skal kunne beskrive:

- relevante aktiver
- trusler og konsekvenser
- ønskede sikkerhedsegenskaber
- kontrolmekanismer
- test og evidens
- residual risiko
- ansvarlig authority

### 16.1 SABSA

Beslutninger bør kunne spores til business attributes som:

- Availability
- Accountability
- Auditability
- Authenticity
- Integrity
- Confidentiality
- Reliability
- Maintainability
- Recoverability
- Traceability
- Privacy
- Longevity

### 16.2 ISO/IEC 27001

Governance skal understøtte risikostyring, adgangskontrol, ændringsstyring, logging, supplier governance, backup, secure development og dokumenteret ansvar.

### 16.3 IEC 62443

Særligt relevante ændringer skal vurdere identification and authentication control, use control, system integrity, data confidentiality, restricted data flow, timely response to events og resource availability.

### 16.4 CRA

Produktændringer skal vurderes i forhold til secure by design, secure by default, sårbarhedshåndtering, autentificerede opdateringer, lifecycle og begrænsning af angrebsfladen.

### 16.5 GDPR

Ændringer, der behandler billeder, identiteter, lokationsdata, logs eller previews, skal vurdere purpose limitation, dataminimering, retention, adgang, transparens og registreredes rettigheder.

### 16.6 AI Act og AI-governance

AI-funktioner skal have tydelig rolle, menneskelig oversight, dataprovenance, logging, begrænsning af autoritet og mulighed for at efterprøve materielle output.

---

## 17. AI Governance i arkitekturprocessen

AI-assistenter må:

- analysere repository og dokumenter
- identificere konflikter og gaps
- foreslå arkitektur og ADR'er
- formulere udkast
- udføre konsistensreview
- foreslå tests og acceptkriterier
- opsummere evidens

AI-assistenter må ikke alene:

- acceptere en ADR
- ændre normative produktprincipper
- acceptere residual risiko
- godkende en sikkerhedsafvigelse
- markere en løsning produktionsklar
- merge destruktive eller højrisikoændringer uden menneskelig authority
- fremstille antagelser som verificerede fakta

AI-bidrag skal være reviewbare og, hvor de er materielle, kunne spores til den konkrete ændring eller handover.

---

## 18. Afvigelser og undtagelser

En afvigelse fra et accepteret princip eller en ADR skal være:

- eksplicit
- tidsbegrænset, hvor muligt
- begrundet
- risikovurderet
- godkendt af relevant authority
- registreret med ejer
- forsynet med udløbsdato eller exit-plan

Midlertidige undtagelser må ikke blive permanente gennem passivitet.

Hvis en implementering ikke kan følge målarkitekturen endnu, skal as-is-afvigelsen beskrives åbent.

---

## 19. Teknisk gæld og arkitekturgæld

Teknisk gæld er ikke automatisk en sikkerhedsrisiko, men den kan øge sandsynligheden for fejl og gøre kontroller sværere at verificere.

Arkitekturgæld opstår blandt andet, når:

- kode omgår definerede kontrakter
- platform- og payloadansvar blandes
- nye interfaces skabes uden ejer og versionering
- midlertidige sikkerhedsundtagelser bliver permanente
- dokumentation og faktisk drift divergerer
- target state beskrives uden en realistisk migrationsvej

Gæld skal registreres med:

- konsekvens
- sandsynlighed
- ejer
- afhængigheder
- foreslået reduktion
- prioritet

---

## 20. Architecture Metrics

Governance skal måles på kvalitet og effekt, ikke dokumentmængde.

Relevante indikatorer kan være:

- andel af væsentlige ændringer med ADR eller dokumenteret rationale
- antal åbne konflikter mellem normative dokumenter og implementering
- tid fra Proposed til beslutning
- antal accepterede ADR'er uden implementerings- eller verifikationsstatus
- coverage af negative sikkerhedstests
- antal tidsudløbne undtagelser
- dokumentationsdrift
- antal uklassificerede dataflows
- antal kontraktbrud fundet i CI
- teknisk og arkitekturel gældstrend
- antal operationelle findings behandlet
- antal Framework Findings valideret eller afvist

Metrics må ikke føre til gaming. Et lavt antal ADR'er er ikke nødvendigvis godt eller dårligt; kvaliteten af beslutningssporbarheden er vigtigere.

---

## 21. Framework Findings

TimeLapse Pro skal fungere som læringsplatform, men Mission Framework må beskyttes mod uprøvede generaliseringer.

Foreslået proces:

```text
Operationel observation
        ↓
Dokumenteret evidens
        ↓
TimeLapse-specifik analyse
        ↓
Arkitekturreview
        ↓
Framework Finding
        ↓
Tværgående vurdering
        ↓
Accept, revision eller afvisning
        ↓
Eventuel optagelse i Mission Framework
```

Et Framework Finding skal mindst beskrive:

- observationen
- evidensen
- den konkrete TimeLapse-kontekst
- hvorfor erfaringen kan være generel
- begrænsninger og modbeviser
- forventet effekt i andre missioner
- anbefalet ændring

TimeLapse-specifikke detaljer skal forblive i produktet, medmindre deres generalitet er demonstreret.

---

## 22. Architecture Governance Board

TimeLapse Pro kan anvende et letvægts Architecture Governance Board som en funktionel model, ikke nødvendigvis som et formelt mødeforum.

Funktionerne er:

- Business Authority
- Architecture Authority
- Security Authority
- Implementation Authority
- Operational Authority
- AI Review Support

For mindre beslutninger kan én person udfylde flere menneskelige roller. Højrisiko- og irreversible beslutninger bør have uafhængigt review eller separation of duties.

Boardets opgave er at sikre:

- at problemet er rigtigt forstået
- at beslutningen er proportional
- at konflikter er synlige
- at ansvar er tydeligt
- at implementerings- og verifikationsvejen er realistisk

---

## 23. Minimum Definition of Done

### 23.1 Architecture Done

- scope og ansvar er klart
- relevante principper og ADR'er er identificeret
- interfaces og trust boundaries er beskrevet
- alternativer og konsekvenser er vurderet

### 23.2 Security Done

- trusselsmodel eller relevant risikoanalyse findes
- fail-closed behaviour er defineret
- identitet, autorisation, audit og secrets er behandlet
- negative testcases er defineret

### 23.3 Governance Done

- status er korrekt
- menneskelig authority er kendt
- konflikter og åbne beslutninger er registreret
- relevante dokumenter er krydsrefereret

### 23.4 Implementation Done

- implementeringen følger kontrakterne
- migrations- og rollbackvej findes
- tests er grønne
- kendte afvigelser er dokumenteret

### 23.5 Operational Done

- runbook og observability findes
- recovery er testet, hvor relevant
- audit og evidens kan hentes
- live-verifikation er gennemført, hvis løsningen afhænger af faktisk hardware eller miljø

---

## 24. Første anvendelse af governance-modellen

Dokumentet bør anvendes på de allerede identificerede spor:

### 24.1 Core Design Principles

Status: Proposed.

Næste governance-trin:

- behandle policykonflikten mellem explicit disposition og eksisterende retention/circular-buffer
- oprette relevante policy-ADR'er
- acceptere, revidere eller afvise principper eksplicit

### 24.2 ADR-002 og ADR-003

ADR-002 ejer kontraktsættet. ADR-003 er reserveret til pakkeformat, signering, isolation og transport.

Næste governance-trin:

- bevare scope-adskillelsen
- undgå at flytte policy ind i kontrakt-ADR'en
- skrive ADR-003, når implementeringsbehovet og alternativerne er modne

### 24.3 Controlled Local Service Access

TPA-00 kan behandles som første inkrement mod målarkitekturen, men ikke som hele den endelige Local Service Gateway-model.

Næste governance-trin:

- dokumentere as-is og target state
- verificere live integrationspunkter
- oprette policy-ADR
- definere migration fra eksisterende adgangsmodel

### 24.4 Evidence Retention and Explicit Disposition

Data-plane-klassifikation og `retention_class` er enableren, men selve policybeslutningen er endnu ikke accepteret.

Næste governance-trin:

- klassificere originale captures, afledte data, logs, cache og telemetry
- beslutte hvilke klasser der er projekt-evidens
- beskrive juridiske og operationelle konsekvenser
- oprette ADR med migrationsplan

---

## 25. TimeLapse Constitution

Følgende dokumenter udgør tilsammen TimeLapse Pro's styrende arkitekturgrundlag:

1. **Core Design Principles** — de normative produkt- og designprincipper.
2. **Architecture Governance** — processen og authority-modellen for arkitekturbeslutninger.
3. **SABSA Security Architecture** — forretningsdrevet sikkerhedsarkitektur og trust model.
4. **Architecture Decision Records** — konkrete, sporbare beslutninger.

De fire lag skal være indbyrdes konsistente og læses før væsentlige systemændringer.

De udgør ikke en statisk forfatning. De kan udvikles, men ændringer skal være dokumenterede, reviewede og ansvarligt accepterede.

---

## 26. Normativ kernesætning

> TimeLapse Pro skal udvikles gennem dokumenterede, reviewbare og evidensbaserede arkitekturbeslutninger. Policy, kontrakter, implementering og drift skal kunne spores til hinanden, og irreversible eller højrisikobeslutninger skal forblive under eksplicit menneskeligt ansvar.

---

## 27. Foreslåede næste handlinger

1. Review dette dokument som **Proposed**.
2. Link det fra onboarding, dokumentoversigt, SABSA og Core Design Principles.
3. Opret ADR for **Controlled Local Service Access**.
4. Opret ADR for **Evidence Retention and Explicit Disposition**.
5. Definér en standard ADR-skabelon med review- og verifikationsfelter.
6. Tilføj statusfelter for Accepted, Implemented og Verified i ADR-registeret.
7. Definér en letvægtsproces for Framework Findings.
8. Brug governance-modellen ved merge og efterfølgende live-verifikation af TPA-00.
