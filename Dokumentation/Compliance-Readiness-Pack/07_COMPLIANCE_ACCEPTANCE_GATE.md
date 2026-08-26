# Compliance Acceptance Gate

**Status:** Praktisk gate for pilot, production og markedskrav

## 1. Pilot gate

Pilot kan accepteres når:

- site-DPIA cover sheet er udfyldt for hvert site;
- TV-overvågningsskiltning/legal basis er kundegodkendt;
- RBAC/adgang til kunden/site er konfigureret;
- retention er besluttet pr. site/kamera;
- update/rollback process er dokumenteret;
- incident/vulnerability contacts er udfyldt;
- kendte P0 er lukket;
- P1 er lukket, de-scoped eller risk-accepted af ejer.

## 2. Controlled production gate

Controlled production kræver ovenstående plus:

- signed release evidence for deployed Headend/Edges;
- SBOM/license evidence for release;
- restore rehearsal med faktisk resultat;
- Edge deployment path uden reprovisioning/destructive credential replacement;
- audit for technician/service operations;
- per-site SFTP ownership hvor aktiveret;
- DPA/controller-processor role matrix udfyldt;
- subprocessorer og cloud-AI region/provider afklaret.

## 3. Market/commercial compliance gate

Bredere markedsføring eller certificeringslignende claims kræver:

- juridisk review af GDPR, TV-overvågning, DPA og markedsclaims;
- CRA product role/classification og conformity file;
- support period policy og vulnerability disclosure public process;
- SBOM/export og third-party notices som release artefacts;
- ISO/IEC/IEC 62443 clause mapping med legitimt kontrolkatalog hvis der claims compliance;
- AI Act classification og AI system inventory pr. aktiveret AI-funktion;
- incident/tabletop og restore rehearsal evidens.

## 4. Red lines

Må ikke claims:

- "ISO 27001 compliant/certified" uden formel ISMS/certificering;
- "IEC 62443 compliant/certified" uden clause-complete mapping og audit;
- "GDPR compliant" som generel garanti uden site-DPIA, DPA og kundens rolleafklaring;
- "CRA ready" uden product classification, support policy, SBOM/release evidence og conformity file;
- "AI Act compliant" uden AI inventory, classification og human oversight evidence.

## 5. Recommended next work order

1. Luk de to konkrete tekniske audit-fund: config fingerprint SHA-256 og dynamic SQL identifier allowlists.
2. Udfyld en rigtig site-DPIA for Frøkjær/Nordre Villavej 17c og Vardevej 26c som pilot.
3. Kør restore rehearsal og dokumenter RTO/RPO.
4. Gør vulnerability/update-SLA offentlig eller kundedelbar.
5. Bind SBOM/license report til den signed release artifact, der faktisk deployes.

