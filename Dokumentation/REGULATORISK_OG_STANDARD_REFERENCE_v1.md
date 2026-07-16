# TimeLapse Pro - regulatorisk og standardmæssigt referencegrundlag

**Version:** 1.0
**Dato:** 2026-07-16
**Status:** Living reference / legal review required before contractual claims
**Ejer:** Produkt- og risikoejer med security/compliance review

> Dokumentet er et teknisk og governance-orienteret horizon scan, ikke juridisk rådgivning. Anvendelsesområde og rolle skal valideres pr. produktvariant, kunde, sektor, land og kontrakt.

## 1. Formål og klassifikation

Referencegrundlaget skal forhindre to fejl: at frivillig best practice fremstilles som lov, og at kommende bindende krav opdages for sent. Hver kilde klassificeres derfor som:

- **A - Direkte bindende eller sandsynligt direkte produktkrav**
- **B - Kundens/sectorens krav, som bliver et leverandørkrav**
- **C - Frivillig standard eller best practice valgt som kontrolgrundlag**
- **H - Horizon watch: forslag, overgang eller standard under udvikling**

Statusord: `gældende`, `vedtaget/indfasning`, `forslag/politisk aftale`, `frivillig`, `betinget scope`.

## 2. Prioriteret konklusion

TimeLapse Pro bør straks udvide sit styrende referencegrundlag med:

1. EU AI Act og NIST AI RMF for AI-governance.
2. EU Data Act for dataadgang, portabilitet, metadata og kontrakter omkring connected products.
3. Det nye produktansvarsdirektiv for software, AI og sikkerhedsopdateringer.
4. Dansk tv-overvågningslov og Datatilsynets arbejdsplads-/overvågningsvejledning som særskilt kamerakontrolspor.
5. NIST CSF 2.0, NIST SP 800-82r3, NIST SSDF og ENISA-guidance som operationel best practice.
6. ISO/IEC 42001 og ISO/IEC 23894 til AI-ledelse og AI-risiko.
7. IEC 62443-4-1/-4-2 for produktudvikling og komponentkrav samt 2-4 for service provider-rollen.
8. EU Cybersecurity Act/certificering, Cyber Solidarity Act og CER som marked-/kundehorisont.
9. RED/Machinery/DORA/energi-/vandregler som betingede vertical-profiler, ikke universelle TimeLapse-krav.

## 3. EU- og dansk lovgivning

| Kilde | Klasse/status pr. 2026-07-16 | Relevans | Krævet handling |
|---|---|---|---|
| GDPR, forordning 2016/679 + dansk databeskyttelseslov | A, gældende | Billeder med identificerbare personer, lokation, bruger-/adgangslogs, AI-tags og cloudbehandling | Rollefordeling, DPA, DPIA pr. site/use case, privacy by design, rettigheder, sletning med lovligt auditspor, overførselsgrundlag og breach-proces |
| Dansk tv-overvågningslov | A, betinget scope | Regelmæssigt gentagen personovervågning med kamera kan være omfattet; offentligt tilgængelige arealer og arbejdspladser kræver særskilt vurdering | Site-screening før aktivering, kameravinkel/masking, skiltning/information, POLCAM-vurdering, adgang/videregivelse/retention og kundens dokumenterede ansvar. [Retsinformation](https://www.retsinformation.dk/eli/lta/2023/182) |
| Datatilsynets vejledning om optagelser og arbejdsplads | A/C, myndighedsvejledning | Byggepladser og andre arbejdssteder kan filme ansatte og tredjeparter | Dokumentér driftsformål, nødvendighed/proportionalitet, medarbejderinformation og hvornår optagelser gennemgås. [Datatilsynet](https://www.datatilsynet.dk/regler-og-vejledning/optagelser-og-overvaagning) |
| EU AI Act, 2024/1689 | A, indfasning | AI-tagging, kvalitetsanalyse, hændelsesalarmer og fremtidig OT-optimering. TimeLapse Pro er typisk AI-system provider og kunde typisk deployer; modelleverandør kan være GPAI-provider | AI-use-case-register, rolle/scope/risk-screening, AI literacy, forbudt-praksis gate, human oversight, logging/proveniens, accuracy/robustness/cybersecurity, transparens og post-market monitoring. Undgå emotion recognition på arbejdspladser og biometrisk inferens. [EU-Kommissionen](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) |
| AI Act tidslinje og AI Omnibus | H, delvist gældende/politisk aftale | Forbud og AI literacy gælder; GPAI-regler gælder. Øvrige datoer påvirkes af 2026-aftalen og endelig lovtekst skal følges | Brug konservativ compliance-baseline nu, men mærk datoer som horizon, indtil ændringsforordningen er endeligt publiceret. Review kvartalsvis og ved ny Official Journal-tekst |
| EU Data Act, 2023/2854 | A, gældende fra 2025-09-12 | Edge/kamera kan være connected product/related service; billeder, telemetri og metadata kan være product/related-service data | Data inventory, kundeadgang i struktureret maskinlæsbart format, relevante metadata, sikker eksport/API, prækontraktuel information, retention og skift/exit. Sikkerhedsundtagelser må være konkrete og dokumenterede. [EUR-Lex](https://eur-lex.europa.eu/eli/reg/2023/2854) |
| Cyber Resilience Act, 2024/2847 | A, vedtaget/indfasning | Kommerciel edge-software/hardware og standalone software kan være products with digital elements. Open source-undtagelsen beskytter ikke automatisk kommerciel distribution/integration | Product classification, manufacturer-role, secure SDLC, SBOM, CVD, supportperiode, security updates, technical file, conformity/CE-plan og incident/vulnerability reporting. Reporting starter 2026-09-11; hovedkrav 2027-12-11. [EUR-Lex](https://eur-lex.europa.eu/EN/legal-content/summary/horizontal-cybersecurity-requirements-for-products-with-digital-elements-cyber-resilience-act.html) |
| NIS 2-direktiv + dansk NIS 2-lov nr. 434/2025 | B og evt. A afhængigt af virksomhed/service; gældende i DK fra 2025-07-01 | Kritiske kunder vil kræve supply-chain security. En fremtidig managed service/security platform kan selv komme i scope afhængigt af tjeneste, størrelse og udpegning | Scope-vurdering årligt og ved forretningsændring; evidence for §6-kontroller, ledelsesansvar, incident reporting, BCM/backup, supplier security, vulnerability handling, MFA/krypto og effektivitetstest. [Retsinformation](https://www.retsinformation.dk/eli/lta/2025/434/dan) |
| CER-direktivet 2022/2557 og dansk sektorimplementering | B, betinget | Kunder som vand, energi og transport kan være critical entities; platformen bliver del af deres fysiske/digitale resilience | Understøt asset/dependency mapping, fysisk sikkerhed, business continuity, kriseøvelser og leverandørevidens; scope pr. vertical. [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022L2557) |
| Nyt produktansvarsdirektiv 2024/2853 | A/H, dansk implementering; produkter efter 2026-12-09 | Software og AI er produkter; opdateringer og relaterede tjenester kan være under fabrikantens kontrol. Manglende nødvendige security updates kan bidrage til defect-vurdering | Safety/security case, dokumenteret support/EOL, update/rollback evidence, kendte risici, change control og bevarelse af teknisk evidens. Open-source komponenter fritager ikke den kommercielle integrator. [EUR-Lex](https://eur-lex.europa.eu/eli/dir/2024/2853/oj/eng) |
| EU Cybersecurity Act 2019/881 + 2025/37 | B/H, gældende | EU-certificering kan blive procurement- eller NIS2-krav; managed security services er nu omfattet af certifikationsrammen | Hold arkitektur/evidens kompatibel med EUCC og kommende managed-service schemes; lov ikke certificering før ekstern vurdering. [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=legissum:4398780) |
| Cyber Solidarity Act 2025/38 | B/H, gældende | EU cyber reserve, fælles beredskab og post-incident review kan påvirke fremtidig OT-security service og kunder | Incident-evidence, samarbejds-/eskaleringsmodel og trusted-provider readiness; ingen direkte produkt-compliancepåstand. [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=LEGISSUM:5773351) |
| RED 2014/53/EU og delegerede cybersikkerhedskrav | A, betinget | Relevant hvis TimeLapse Pro markedsfører egen radio-/Wi-Fi-/Bluetooth-/4G-hardware som radioudstyr/fabrikant, ikke blot bruger CE-mærket standardhardware | Afklar economic operator og produktintegration; radio, safety, privacy, fraud og conformity assessment må ind i hardware-verticalens technical file |
| Machinery Regulation 2023/1230 | A/B, betinget, anvendes fra 2027 | Relevant hvis fremtidig OT-payload kontrollerer maskiner eller bliver safety component | Separat machinery/safety lifecycle; AI/cybersecurity må aldrig erstatte funktionel sikkerhed; kræv hazard analysis og kvalificeret conformity route |
| eIDAS2 / European Digital Identity framework | C/H | Kan støtte stærk leverandør-/administratoridentitet og signatures, men er ikke nødvendig for intern PKI | Følg wallet/qualified trust service-muligheder; behold crypto-agility og adskil device-, human- og release-identitet |
| DORA 2022/2554 | B, sektorbetinget | Finansielle kunder kan stille DORA-krav til ICT third-party providers | Kontraktbilag, registerdata, testing, incident support, exit og subcontractor transparency pr. finansiel kunde |
| Energy/water/telecom/transport sector rules | B, verticalbetinget | Fremtidige OT-payloads kan falde under sektorspecifik dansk lov i stedet for generel NIS2-lov | Opret regulatory profile pr. vertical før kode/pilot; ingen universel claim baseret alene på NIS2 |
| Markedsførings-, forbruger-, tilgængeligheds- og kontraktret | A/B, forretningsmodelbetinget | Website, claims, abonnement, supportperiode og eventuel B2C | Underbyg security/compliance/AI-claims; klare service- og exitvilkår; accessibility review af kundeportal |

## 4. AI Act-screening for aktuelle funktioner

| Use case | Foreløbig klassifikation | Kontrol |
|---|---|---|
| Tags om byggeaktivitet, vejr, lys og billedkvalitet | Begrænset/minimal risiko, med GDPR afhængigt af motiv | AI-label/proveniens, confidence, menneskelig korrektion, model/prompt/version, ingen personprofilering |
| AI-baseret billedoptimering og kameraoffset | Normal produkt-AI; kan blive safety-relevant i OT-vertical | Bounded actions, rollback, change log, deterministic guardrails og human override |
| Person-/køretøjsdetektion til søgning | GDPR + AI Act-screening; ikke automatisk biometrisk identifikation | Dataminimering, formålsbinding, retention, DPIA, ingen protected-attribute inferens |
| "Uvedkommende", adfærd eller anomali på arbejdsplads | Høj juridisk/fundamental-rights risiko | Deaktivér som default; særskilt legal/DPIA/AI Act-screening og human verification. Ingen emotion recognition |
| SIEM/CMDB copilot | Begrænset operationel AI | Read-only default, citeret evidens, ingen autonom privilegeret handling, prompt-injection controls |
| Fremtidig autonom OT-kontrol | Potentielt high-risk/safety critical afhængigt af use case | Ny ADR, safety/security co-engineering, sector law, independent assessment; må ikke arve TimeLapse-godkendelse |

Der skal være et AI system/use-case register med: owner, purpose, provider/deployer/GPAI roller, model og licens, data categories, legal basis, risk class, human oversight, metrics, known limitations, incident path, change history og retirement.

Danmark tilbyder en regulatorisk AI-sandkasse gennem Datatilsynet og Digitaliseringsstyrelsen. Den bør overvejes før person-/arbejdspladsanalyse eller OT-autonomi. [Datatilsynet](https://www.datatilsynet.dk/regler-og-vejledning/kunstig-intelligens/regulatorisk-sandkasse)

## 5. Styrende standarder og frameworks

### 5.1 Behold som primære

- **SABSA:** business attributes, traceability fra forretning til security services og assurance.
- **COBIT 2019:** governance objectives, ansvar, performance og ledelsesrapportering.
- **ISO/IEC 27001:2022 + 27002:2022:** ISMS og kontrolkatalog.
- **ISO/IEC 27005:** informationssikkerhedsrisiko.
- **ISO 22301:** business continuity og øvelser.
- **ISO/IEC 27701:** privacy information management; nyttig til GDPR-evidens.
- **IEC 62443-serien:** OT/industrial automation security.

### 5.2 IEC 62443-profil pr. rolle

- **62443-4-1:** secure product development lifecycle - central for platform/payload og CRA.
- **62443-4-2:** technical security requirements for IACS components - relevant for Edge/platform component claims.
- **62443-3-2/-3-3:** system risk assessment, zones/conduits og system security requirements.
- **62443-2-4:** krav til IACS service providers - central ved remote support og fremtidige leverandører.
- **62443-2-1:** asset-owner security programme - primært kundens ansvar, men produktet skal levere evidens.
- Security Level-claims må ikke gives uden defineret scope, threat model og evidens/assessment.

### 5.3 Tilføj for AI

- **ISO/IEC 42001:** AI management system; governance, lifecycle, impact og continual improvement.
- **ISO/IEC 23894:** AI risk management.
- **NIST AI RMF 1.0 + Playbook:** Govern, Map, Measure, Manage; brug som operationel AI-evidence model. NIST er i gang med revision og en critical-infrastructure profile, som skal overvåges. [NIST](https://www.nist.gov/itl/ai-risk-management-framework)
- **NIST AI 600-1:** generativ AI-profile for hallucination, information integrity, privacy, misuse og TEVV.

### 5.4 Tilføj for cyber og OT

- **NIST CSF 2.0:** fælles GRC-navigation via Govern, Identify, Protect, Detect, Respond, Recover. Brug som indeks/crosswalk, ikke som certificeringspåstand. [NIST](https://www.nist.gov/publications/nist-cybersecurity-framework-csf-20)
- **NIST SP 800-82 Rev. 3:** OT-topologier, safety/reliability constraints og OT-control overlay. [NIST](https://csrc.nist.gov/pubs/sp/800/82/r3/final)
- **NIST SP 800-218 SSDF:** secure SDLC og supplier vocabulary; map direkte til CRA/IEC 62443-4-1. [NIST](https://csrc.nist.gov/pubs/sp/800/218/final)
- **NIST SP 800-161r1:** cyber supply-chain risk management.
- **NIST SP 800-61r3:** incident response koblet til CSF 2.0.
- **NIST SP 800-207:** Zero Trust; brug principper, men OT-safety og offline drift har forrang.
- **NIST SP 800-53r5:** dybt kontrolbibliotek/informative mapping, ikke universel baseline.
- **NISTIR 8286-serien:** kobling mellem cyberrisiko og enterprise risk/FAIR-input.

### 5.5 ENISA og europæisk implementering

- **ENISA NIS2 Technical Implementation Guidance:** praktiske evidenseksempler og mappings, især hvis platformen bliver managed service provider. [ENISA](https://www.enisa.europa.eu/publications/nis2-technical-implementation-guidance)
- **ENISA Good Practices for Supply Chain Cybersecurity:** supplier lifecycle, dependency, EOL og monitoring. [ENISA](https://www.enisa.europa.eu/publications/good-practices-for-supply-chain-cybersecurity)
- **ENISA IoT secure supply chain/secure SDLC:** relevant for Edge images, hardware og tredjepartspayloads.
- **ENISA Threat Landscape/NIS360:** årligt threat- og sector-horizon input; ikke et kontrolkatalog.
- **SAMSΙK vejledning om leverandørforhold:** dansk kontrakt- og supplier governance. [SAMSΙK](https://samsik.dk/cyb-publikationer/cybersikkerhed-i-leverandoerforhold/)

### 5.6 Engineering-baselines

- OWASP ASVS, API Security Top 10, MASVS hvor relevant, og IoT Security Verification Standard.
- CIS Controls v8 og CIS Benchmarks for konkrete hardening checks.
- SPDX eller CycloneDX for SBOM; CSAF for advisories og VEX for exploitability status.
- SLSA, in-toto/Sigstore-principper og OpenSSF Scorecard for build/provenance/supply-chain maturity.
- CVSS må ikke stå alene: kombiner CVSS, EPSS, CISA KEV, asset exposure, reachability og SSVC-lignende beslutningslogik. FAIR bruges til kvantitativ forretningsrisiko, når input er valideret.
- ETSI EN 303 645 + ETSI TS 103 701 er nyttig IoT-baseline/testmetode, men er ikke i sig selv CRA-conformity. [ETSI](https://www.etsi.org/newsroom/press-releases/2457-etsi-releases-new-guidelines-to-enhance-cyber-security-for-consumer-iot-devices/)

## 6. Kontrolarkitektur for en fremtidig open-source OT-platform

Open source og et multi-vendor-økosystem kræver mere, ikke mindre, trust governance:

1. **Roller:** platform manufacturer/maintainer, payload supplier, integrator, service provider, asset owner og operator registreres separat.
2. **Delegated trust:** leverandørnøgler har scope til navngiven payload, version, kunde/miljø og handling; ingen global platformtrust.
3. **Promotion:** supplier -> lab -> staging -> customer approval -> production med immutable provenance og test evidence.
4. **Support:** JIT-ticket, kortlivet identitet, destinations-/kommandoallowlist, recording/audit, revocation og kill switch.
5. **Product evidence:** SBOM/VEX/licens, supportperiode, CVD/PSIRT, release notes, known issues, rollback og reproducible/attested build hvor muligt.
6. **Data governance:** payloadmanifest deklarerer dataklasse og behov; platformpolicy godkender adgang, eksport, retention og cloud transfer.
7. **Isolation:** separat proces/sandbox og resource/network/file policy; manifest er ikke enforcement.
8. **Liability:** kontrakter og technical file viser ansvar på tværs af supplier/integrator/manufacturer, især når open-source kode bruges kommercielt.

## 7. Krav til GRC/CMDB/UI

Referencegrundlaget bør operationaliseres som data, ikke kun tekst:

- `framework`, `instrument_id`, `jurisdiction`, `status`, `effective_from`, `review_date`, `source_url`.
- `applicability`: direct, customer-driven, conditional, voluntary, horizon.
- `role`: manufacturer, provider, deployer, data controller/processor, service provider, asset owner.
- mapping fra requirement/control til asset, policy, test, artifact, owner og evidence timestamp.
- claims må have status `not assessed`, `gap`, `implemented`, `tested`, `independently assessed` eller `certified`; `implemented` må aldrig vises som certificeret.
- regulatory horizon-dashboard med ændringer, deadline, impact, owner og beslutning.
- rapporter skal genereres fra samme evidensgraf, så overlap genbruges i stedet for at kopiere bevis.

## 8. Regulatory horizon watch

| Emne | Næste trigger | Frekvens |
|---|---|---|
| AI Act/AI Omnibus og harmoniserede standarder | Endelig ændringsforordning, transparency/high-risk guidance og standarder | Månedligt til 2028 |
| CRA | Reportingplatform/guidance, harmoniserede standarder, important/critical classification | Månedligt til 2027 |
| Dansk implementering af produktansvarsdirektivet | Lovforslag og vedtagelse før 2026-12-09 | Kvartalsvis |
| Data Act | Dansk/EU enforcement og connected-product guidance | Kvartalsvis |
| NIS2/DK bekendtgørelser og sektorvejledning | Nye krav, myndigheder og tilsynspraksis | Kvartalsvis |
| EU cybersecurity certification | EUCC, cloud/MSS schemes og procurementkrav | Kvartalsvis |
| NIST AI RMF revision + critical infrastructure profile | Draft/final publication | Kvartalsvis |
| ENISA threat landscape/NIS360 | Ny årsrapport eller sector profile | Årligt + eventdrevet |
| Nye verticals | Før proof-of-concept eller kundepilot | Obligatorisk scope review |

Kun officielle eller normative kilder må ændre legal status. Blogs og leverandørfortolkninger kan bruges til discovery, ikke som juridisk evidens.

## 9. Konkrete næste handlinger

1. Tilføj AI Act, Data Act, produktansvar, tv-overvågning, NIST og ENISA til dokumentpakke- og standardindeks.
2. Opret et AI use-case register og gennemfør første AI Act/GDPR-screening for tagging, persondetektion, SIEM-copilot og autonom kameraoptimering.
3. Opret CRA product-role/classification memo for Headend software, Edge image/appliance og en mulig open-source platformdistribution.
4. Opret Data Act data inventory og standardiseret kundeeksport/API med metadata og audit.
5. Map eksisterende evidence én gang til ISO 27001, IEC 62443, CRA, NIS2, NIST CSF og SSDF.
6. Opret vertical regulatory profile template før vand/energi/maskinefunktioner implementeres.
7. Få ekstern dansk/EU juridisk validering før internet-go-live/kommerciel lancering og før claims om compliance eller CE.

## 10. Kildeprincip

Primære kilder er EUR-Lex/Official Journal, Retsinformation, kompetente danske myndigheder, EU-Kommissionen/AI Office, ENISA, NIST, ISO/IEC/ETSI og relevante tilsyn. Kildedato og access/review-dato skal gemmes i GRC-systemet, fordi dette felt ændrer sig hurtigt.
