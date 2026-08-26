# Customer/Site DPIA Pack

**Status:** Skabelon til udfyldelse pr. kunde/site  
**Vigtigt:** Ikke juridisk rådgivning. Kunden/dataansvarlig bør godkende formål, hjemmel, skiltning og opbevaringsperioder.

## 1. Site cover sheet

| Felt | Udfyldes |
|---|---|
| Kunde | |
| Site/navn | |
| Adresse/GPS | |
| Kamera/device-id | |
| Formål | Fremdriftsdokumentation / dokumentation / andet: |
| Dataansvarlig | Kunden, hvis kunden bestemmer formål og midler |
| Databehandler | TimeLapse Pro/Froekjaer, hvis TLP behandler data på kundens vegne |
| Kontakt hos kunde | |
| Kontakt hos TLP | |
| DPIA dato | |
| Næste review | |

## 2. Behandling

| Område | Beskrivelse |
|---|---|
| Primære data | Periodiske billeder fra fast monteret kamera |
| Mulige persondata | Personer, køretøjer, nummerplader, lokation/tidspunkt |
| Metadata | Device-id, site, kamera, capture-tidspunkt, upload-status, kvalitet, audit |
| AI-data | Tags, billedkvalitet, scene-/diagnostikmetadata hvor aktiveret |
| Modtagere | Kunden, autoriserede TLP-admins/teknikere, eventuelle subprocessorer |
| Overførsel | Headend/API, eventuelt kunde-SFTP pr. site |
| Automatiske afgørelser | Nej, AI må ikke træffe irreversible beslutninger om personer |

## 3. Nødvendighed og proportionalitet

| Kontrolpunkt | Status | Note |
|---|---|---|
| Formålet er dokumenteret | Ikke udfyldt | Kunden udfylder |
| Synsfelt er begrænset til nødvendigt område | Ikke udfyldt | Verificeres ved commissioning |
| Offentlig vej/naboareal undgås hvor muligt | Ikke udfyldt | Kræver site-vurdering |
| Capture-interval er proportionalt | Ikke udfyldt | Typisk 5-15 min, men site-bestemt |
| Retention er sat pr. kamera/site | Ikke udfyldt | Se retention-afsnit |
| Adgang er rollebaseret | Delvist teknisk understøttet | Verificeres i RBAC/CMDB |
| Kunde-SFTP er site-specifik | Delvist teknisk understøttet | Skal verificeres pr. site |

## 4. Retention og disposition

| Datatype | Standardforslag | Beslutning pr. site |
|---|---:|---|
| Projektbilleder på Headend | Indtil projektets formål er opfyldt + aftalt reklamations-/dokumentationsperiode | |
| Edge-lokal buffer | FIFO når billedet er bekræftet overført via alle aktiverede transportspor | |
| Auditlogs | Minimum sikkerheds-/driftsbehov; bør fastsættes kontraktuelt | |
| AI-tags/metadata | Samme eller kortere end billedgrundlag, medmindre kontrakt kræver andet | |
| Diagnostic bundles | Kort operationel periode, med manuel forlængelse ved incident | |

## 5. TV-overvågning/site-notice

Før installation skal kunden bekræfte:

- der er et legitimt og dokumenteret formål;
- kameraet placeres og vinklen sættes så optagelse begrænses;
- skiltning/information er på plads før optagelse;
- kontaktpunkt og opbevaringsperiode fremgår af kundens information;
- adgang til billeder er begrænset til autoriserede personer.

Forslag til kort skiltetekst, der skal juridisk/kundemæssigt godkendes:

> Denne byggeplads fotograferes periodisk til fremdrifts- og projektdokumentation. Dataansvarlig: [KUNDE]. Databehandler: TimeLapse Pro/Froekjaer. Billeder opbevares i [PERIODE]. Kontakt: [KONTAKT].

## 6. Risk register pr. site

| Risiko | Sandsynlighed | Konsekvens | Kontrol | Residual risk |
|---|---|---|---|---|
| Utilsigtet optagelse af personer/offentligt område | Middel | Middel | FOV-review, skiltning, retention | |
| Uautoriseret adgang til billeder | Lav/middel | Høj | MFA/RBAC/audit/tenant-isolation | |
| For lang opbevaring | Middel | Middel | Retention pr. kamera/site | |
| Forkert kunde/site-SFTP | Lav/middel | Høj | Per-site SFTP profil og RBAC ownership | |
| Cloud-AI behandling uden korrekt aftale/region | Lav/middel | Høj | AI-register, region/processor review | |

## 7. Site approval

| Rolle | Navn | Dato | Godkendelse |
|---|---|---|---|
| Kunde/dataansvarlig | | | |
| TLP teknisk ansvarlig | | | |
| Juridisk/privacy review hvis relevant | | | |

