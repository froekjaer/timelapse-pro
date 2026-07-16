# Compliance Regulatory Intelligence & Audit - målarkitektur

**Version:** 1.0
**Dato:** 2026-07-16
**Status:** Proposed, fase 0 implementeret

## Formål

Compliance-menuen skal kunne vedligeholde et versionsstyret globalt register over lovgivning, standarder og best practice samt gennemføre reproducerbare audits mod hele det valgte og anvendelige kravkatalog. Systemet må aldrig forveksle et TimeLapse-specifikt udsnit med en fuld standardaudit.

## Principper

1. Officiel kilde frem for blog eller leverandørfortolkning.
2. Metadata, originaltekst, normaliseret krav og TimeLapse-mapping er separate lag.
3. Eksterne ændringer aktiveres aldrig automatisk: hent -> hash -> diff -> review -> godkendt baseline.
4. Alle audits bindes til catalog version/hash, scope, rolle, profil, tidspunkt og evidence snapshot.
5. `implemented`, `tested`, `independently_assessed` og `certified` er forskellige statusser.
6. Proprietære standarder importeres kun fra en legitim licenseret kilde eller kundeimport; produktet redistribuerer ikke standardteksten.
7. Applicability afgøres før compliance: jurisdiktion, sektor, virksomhedsstørrelse, economic-operator role, produktklasse, AI-use-case og kontrakt.

## Informationsmodel

- `RegulatoryInstrument`: lov/forordning/direktiv/order/standard/framework, jurisdiktion, status og deadlines.
- `SourceSnapshot`: URL, retrieved_at, content hash, format, signer/TLS metadata og immutable original.
- `InstrumentVersion`: Official Journal/effective version, predecessor/successor og change summary.
- `Requirement`: stabil requirement ID, hierarchy, normative level, effective dates og source locator.
- `ApplicabilityProfile`: product/customer/vertical/role/jurisdiction med begrundelse og approver.
- `ControlObjective`: fælles intern kontrol, som flere requirements kan mappe til.
- `RequirementMapping`: requirement -> control/test/evidence/policy/owner med mapping confidence og review.
- `Evidence`: type, asset/scope, collector, hash, freshness, access class og result.
- `AuditRun`: catalog hash, applicability profile, evidence snapshot, assessor og finding set.
- `Finding`: conforming/partial/nonconforming/not_applicable/not_tested med severity, remediation og acceptance.

## Kildeconnectors

- EU: EUR-Lex/ELI/Cellar og EU-Kommissionens policy/horizon-sider.
- Danmark: Retsinformation og kompetente myndigheder (SAMSΙK, Datatilsynet, sektorregulatorer).
- USA/energi: NERC effective standards, FERC orders og implementation plans.
- NIST/ENISA: officielle publiceringsregistre og maskinlæsbare catalogs hvor tilgængeligt.
- ISO/IEC/SABSA: licenseret/kundeimporteret content package; ingen automatisk scraping eller redistribution.

Connectors kører i en isoleret ingestion worker uden produktionsdatabase-write. De afleverer en kandidatpakke til review. Headend kan fortsat fungere helt offline med seneste godkendte snapshot.

## Auditflow

1. Vælg standard/instrument og præcis version.
2. Vælg scope: platform, Headend, Edge, payload, kunde, site, leverandør eller vertical.
3. Udfyld applicability questionnaire og godkend profil.
4. Systemet viser catalog completeness; fuld audit blokeres ved manglende requirements/licens.
5. Frys evidence snapshot og kør automatiske tests/mappings.
6. Assessor behandler alle requirements, herunder `not applicable` med begrundelse.
7. Findings bliver change tickets/risk acceptances med owner og deadline.
8. Rapport signeres og kan reproduceres fra catalog/evidence hashes.

## Audittyper

- `readiness`: alle krav gennemgås, men ikke en certificeringspåstand.
- `internal`: dokumenteret intern audit med assessor independence.
- `supplier`: kundens eller platformens leverandøraudit.
- `external`: import af tredjepartsassessors findings/evidence.
- `certification`: må kun registreres med certifikat, scope, organ og udløb; genereres aldrig af TimeLapse Pro selv.

## Global baseline og profiler

Den fælles kontrolgraf bør mindst kunne mappes til EU/DK, NIST og NERC. Jurisdiktionsprofiler tilføjes efter marked: USA (NERC CIP/NIST), UK (NIS Regulations/PSTI/UK GDPR), Canada, Australien og andre kun efter konkret salgs-/produktplan. En global liste er discovery; et audit kræver valgt jurisdiction/sector/effective version.

## Implementeringsfaser

- **Fase 0 - udført:** versioneret metadataregister, autoritative links, UI-søgning og ærligt audit-catalog readiness.
- **Fase 1:** PostgreSQL-model/migration, admin review, source snapshots og change history.
- **Fase 2:** EUR-Lex/Retsinformation/NIST/NERC connectors med allowlist, hashes og diff.
- **Fase 3:** requirement/control/evidence graph og applicability profiler.
- **Fase 4:** clause-complete readiness/internal audit, findings og signerede rapporter.
- **Fase 5:** licenseret ISO/IEC import, supplier portal og multi-vendor evidence exchange.

## Fase 0-begrænsning

Det aktuelle registry i `headend/compliance_intelligence.py` er et reviewed seed og ikke endnu dynamisk persisted. UI viser korrekt, at ingen kataloger endnu er `complete_verified`. De eksisterende fem standardrapporter er fokuserede TimeLapse evidence views og må omdøbes/markeres som `partial mapping`, indtil auditmotoren er på plads.
