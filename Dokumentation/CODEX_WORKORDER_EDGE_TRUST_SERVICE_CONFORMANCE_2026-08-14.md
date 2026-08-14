# Codex Work Order — TimeLapse Pro Edge Trust, Provisioning & Service Conformance Review

**Dato:** 2026-08-14  
**Repository:** `froekjaer/timelapse-pro`  
**Status:** Proposed review work order  
**Scope:** Review først. Ingen bred feature-udvikling eller refaktorering som del af assessmentet.

## Formål

Gennemfør et **code-backed, repository-wide architecture conformance review** af TimeLapse Pro mod den senest aftalte målmodel for Edge identity, enrollment, credentials, technician service lifecycle, local service access, PKI, RBAC/capabilities, provisioning, commissioning og decommissioning.

Den vigtigste regel for opgaven er:

> **Find kontrakten først. Ret derefter implementationen.**

Målet er ikke endnu en serie lokale fixes, men en kontrolleret migration fra den nuværende implementation til en sammenhængende, testbar og maskin-håndhævet Edge trust-, provisioning- og servicearkitektur.

## 1. Baseline og kilder

Læs som minimum:

- `Dokumentation/HANDOVER_LOG.md`
- `Dokumentation/00_START_HER.md`
- `Dokumentation/ADR/ADR-001-platform-payload-split.md`
- ADR-002 og den reserverede ADR-003-model
- `Dokumentation/Arkitektur/TimeLapse_Core_Design_Principles_v1.md` fra PR #5
- `Dokumentation/Arkitektur/TimeLapse_Architecture_Governance_v1.md` fra PR #6
- `Dokumentation/RBAC_Remote_Operational_v10.md`
- `Dokumentation/EDGE_GENERATOR_REVIEW_2026-08-03.md`
- relevante SABSA-, Risk-, Configuration-, Edge Runbook- og Security-dokumenter

Gennemgå også `main` samt aktive/open PR'er og branches, især PR #8 og PR #9, hvis de fortsat er relevante. Rapportér eksplicit hvor dokumentation og implementation beskriver forskellige modeller.

## 2. Target model — Edge Identity, Enrollment and Credential Lifecycle

Én fælles lifecycle authority skal styre:

`prepare → provision → bootstrap → hardware verify → enroll → credential → assign → activate → rotate → recover → revoke → retire`

Reviewet skal svare på:

- Hvem ejer den autoritative Device Identity?
- Hvordan anvendes MAC/hardware identity?
- Hvor genereres private keys?
- Hvilke private keys findes på Headend?
- Hvilke ligger i image?
- Hvilke genereres på Edge?
- Hvordan roteres og revokes credentials?
- Hvordan håndteres hardware replacement?
- Hvordan forhindres duplicate/cloned identities?

Target-princip: Device identity er Headend-governed og hardware-bound. Hardware-attributter er evidence/binding — ikke alene den autoritative logiske identitet.

## 3. Credential- og trust-path inventory

Kortlæg samtlige credentials som minimum for:

- Device API Identity — Edge → Headend API
- Device Support/Tunnel Identity — Edge ↔ reverse/support tunnel
- Local Service Identity — Technician → Edge
- Bootstrap Identity — enrollment/bootstrap
- Update/Release Trust — artifact verification/signing
- Local TLS Identity — Edge HTTPS server certificate
- User/Technician Identity — personlig Headend identity + MFA

For hver credential dokumenteres:

- issuer
- subject
- owner
- private-key location
- public-key location
- storage
- lifetime
- scope
- audience
- rotation
- revocation
- backup
- compromise procedure
- lifecycle state hvor credential oprettes og destrueres

Flag credential reuse og uklart ejerskab som arkitekturafvigelser.

## 4. SSH model — reconciliation krævet

Kortlæg den faktiske implementation af:

- Headend-genereret device SSH key
- Edge-genereret SSH key ved first boot
- image-injected SSH key
- shared/break-glass support key
- reverse tunnel
- browserbaseret SSH terminal

Svar eksplicit:

1. Hvem ejer Edgeens permanente SSH private key?
2. Hvor findes den?
3. Hvor mange SSH identities findes?
4. Hvilke kan logge ind hvor?
5. Hvilken rolle spiller reverse tunnel?
6. Er host keys pinned?
7. Er support-access personligt eller delt?
8. Hvordan gennemføres rotation?
9. Hvordan revokes en kompromitteret tekniker?
10. Kan en credential anvendes på flere Edges?

Anbefal én target model.

## 5. Device API identity

Kortlæg:

- bootstrap token
- enrollment response
- device API token
- config token
- lagringssteder
- token duplication
- rotation
- expiry
- revocation
- re-enrollment

Kontrollér specifikt om samme API-token lagres flere steder. Anbefal en canonical credential store.

## 6. PKI / Edge Local CA

Review mindst:

- `headend/services/edge_local_pki.py`
- CA API'et
- image integration
- lokal TLS
- mDNS
- Apple trust profile

Vurder:

- CA lifecycle
- root key protection
- leaf lifecycle
- issuance policy
- expiry
- rotation
- revocation
- Edge decommission
- CA compromise/recovery
- replacement Edge
- duplicate identity
- audit
- backup

Certificate issuance skal være koblet til en accepteret device lifecycle state og ikke være en løs utility-operation.

## 7. Authorization — RBAC + capabilities + context

Kortlæg den faktiske authorization model.

Target decision model:

`Principal + Role + Capability + Tenant/Customer + Resource Ownership + MFA + Context → Allow/Deny`

Undersøg bl.a.:

- `require_role`
- `on_site_service`
- technician permissions
- customer isolation
- admin/super_admin bypasses
- MFA state
- local service permissions
- PKI endpoints
- SSH endpoints
- update endpoints
- GPIO/hardware actions
- terminal
- preview
- camera configuration

Find ad hoc authorization expressions i endpoints og registrér dem som kandidater til et centralt Policy Decision Point.

## 8. Edge Service Lifecycle and Technician Experience

Review hele teknikerrejsen som én platform capability.

### Fase 1 — Workshop Preparation

Teknikeren skal kunne:

- vælge Edge/hardware
- vælge kamera/site/customer
- vælge godkendt release
- konfigurere bootstrap
- skrive image
- kontrollere artifact/signatur
- køre preflight
- producere en Preparation Report

### Fase 2 — Bench Commissioning

Én samlet commissioning-test bør validere:

- identity
- hardware
- storage
- camera
- modem
- GPS
- relays
- network
- local TLS
- mDNS
- Headend
- API
- time
- certificates
- update
- local service

### Fase 3 — Site Commissioning

Løsningen skal fungere på mobil, med dårligt net og også uden fungerende Headend/modem. Normale opgaver må ikke kræve shell.

### Fase 4 — Operational Maintenance

Teknikeren skal kunne diagnosticere Edge uden at kende Linux-internals.

### Fase 5 — Remote Support

Kontrolleret JIT/support conduit.

### Fase 6 — Offline/Break-glass Recovery

Separat trust path med begrænset scope og stærk audit.

### Fase 7 — Hardware Replacement

Edge board, storage, modem og kamera skal kunne udskiftes uden at miste logisk projektidentitet/historik.

### Fase 8 — Decommission

Credentials skal revokes, mens relevant audit/evidence bevares.

## 9. Local Service Gateway

Vurder den nuværende implementation mod princippet:

> **One Local Service Gateway; multiple transports.**

Transport kan være Bluetooth PAN, Wi-Fi, Ethernet eller USB networking. Auth, policy, sessions, capabilities, audit og service API skal være fælles. Find duplikerede transport-specifikke security paths.

## 10. `edge/scripts/totp-service.py`

Lav et særskilt architecture review. Filen ser ud til at eje mange ansvarsområder, herunder auth, sessions, firewall, TOTP, local portal, camera, live view, shell, network, service policy, maintenance, HTML og video.

Vurder om den er ved at blive Edge-versionen af `headend/main.py`.

Foreslå target decomposition, fx:

- `local_service/gateway`
- `local_service/auth`
- `local_service/session`
- `local_service/policy`
- `local_service/audit`
- `local_service/api`
- `local_service/diagnostics`
- `local_service/network`

Timelapse-specifikke servicefunktioner skal placeres i payload-domænet.

Ingen refaktorering i assessmentet.

## 11. Technician Authentication

Review `edge/technician_auth.py` end-to-end.

Kontrollér bl.a.:

- object/dict inconsistencies
- challenge lifecycle
- replay protection
- callback authentication
- token audience
- token persistence
- session expiry
- restart
- multiple sessions
- technician revocation

En almindelig Headend session/JWT må ikke bruges som permanent lokal Edge credential.

Target: Headend udsteder et kortlivet `EdgeServiceGrant` bundet til:

- technician identity
- Edge ID
- allowed capabilities
- MFA state
- tenant/customer scope
- expiry
- nonce/session
- purpose

Grant'et må ikke kunne genbruges mod almindelige Headend APIs.

## 12. Shell og terminal

Vurder alle shell-/terminalfunktioner mod princippet:

> **Normal field service SHALL NOT require shell access.**

Shell er break-glass/senior engineering capability og bør kræve personlig identity, MFA/step-up, purpose, kort TTL, audit, sessionsregistrering, destination restriction, host-key validation, credential isolation og revocation.

Review især browserbaseret SSH-terminal i PR #9 og klassificér den som normal service, engineering eller break-glass. Vurder om en shared break-glass-key model er acceptabel.

## 13. Edge Generator Architecture

Vurder om generatoren blander:

- release build
- OS artifact
- device provisioning
- credentials
- customer/site configuration
- networking
- PKI
- SSH
- camera binding

Target separation:

`Release Artifact Builder` → generic signed TimeLapse runtime  
`Device Provisioning Service` → device-specific intent  
`Credential Issuer` → bootstrap/trust material  
`Flash Composer` → final install medium

Vurder migration fra “unikt OS-image pr. Edge” mod “generic signed Edge image + small signed device provisioning envelope”. Ingen implementation endnu.

## 14. Canonical Provisioning State Machine

Design en canonical state machine med mindst:

- manufactured
- prepared
- media_written
- bootstrap_pending
- bootstrap_authenticated
- hardware_verified
- enrolled
- credentialed
- assigned
- active
- degraded
- quarantined
- revoked
- retired

For hver transition dokumenteres:

- trigger
- preconditions
- actor
- credential required
- resulting credentials
- audit event
- recovery path
- rollback/retry
- forbidden transitions

Identificér hvor den aktuelle kode bruger implicit state eller boolske flags i stedet.

## 15. Serviceability som platform capability

Skeln mellem:

### Platform service

- identity
- auth
- network
- health
- logs
- update
- storage
- time
- certificates
- local access
- tunnel
- audit

### TimeLapse payload service

- camera
- focus
- exposure
- capture-test
- image QA
- live preview

Rapportér funktioner placeret i forkert domæne i forhold til ADR-001.

## 16. Commissioning Contract

Design target for `CommissioningReport v1` med mindst:

- identity verified
- hardware verified
- correct customer/site
- software release
- artifact signature
- SBOM
- camera
- test capture
- image QA
- modem
- network
- GPS
- time
- storage
- local TLS
- remote connectivity
- service access
- update
- technician
- date/time
- deviations

Output:

- PASS
- PASS WITH DEVIATIONS
- FAIL

Commissioning må ikke blive PASS alene på baggrund af UI-status.

## 17. Service Record / Mission pattern

Design target for persistent servicehistorik:

`Need → Observation → Evidence → Diagnosis → Decision → Action → Verification → Outcome`

Vurder hvordan dette kan mappe til Mission Framework og hvilke elementer der er generiske nok til Framework Findings.

## 18. Current vs Target Matrix

Lav en central tabel:

| Domain | Current | Target | Gap | Risk | Recommendation | Priority |
|---|---|---|---|---|---|---|

Minimum domains:

- device identity
- bootstrap
- API credentials
- SSH identity
- local TLS
- technician identity
- RBAC
- capabilities
- MFA
- offline access
- Bluetooth
- WiFi
- Ethernet
- local portal
- diagnostics
- shell
- remote support
- generator
- release artifact
- commissioning
- service history
- replacement
- decommission
- audit
- certificate rotation
- credential revocation

## 19. Prioritering

Brug:

- **P0:** security/integrity problem that can invalidate trust or allow incorrect access
- **P1:** architecture/lifecycle flaw likely to cause repeated field failures or unsafe recovery
- **P2:** structural technical debt
- **P3:** UX/maintainability improvement

Hold **bug** adskilt fra **architecture decision required**.

## 20. ADR-anbefalinger

Reviewet skal udarbejde outline og scope-reconciliation til tre Proposed ADR'er:

### ADR — Edge Identity, Enrollment and Credential Lifecycle

Ejer device identity, bootstrap, API identity, SSH/tunnel identity, credential generation, rotation, revocation, replacement og retirement.

### ADR — Edge Service Lifecycle and Technician Experience

Ejer preparation, commissioning, site installation, maintenance, remote support, offline recovery, replacement, decommission og technician UX.

### ADR — Controlled Local Service Access

Ejer Local Service Gateway, physical presence, transports, sessions, authentication, authorization, offline/break-glass access og audit.

ADR'erne skal koordineres med ADR-001/002/003 og må ikke overtage deres scope.

## 21. Review mode — ingen bred featureudvikling

Du skal først levere reviewet.

Du må ikke som del af assessmentet:

- redesigne hele auth-systemet
- migrere credentials
- erstatte SSH
- refaktorere `totp-service.py`
- ændre PKI
- ændre generatoren
- merge PR #9

Hvis du finder P0:

1. dokumentér det
2. foreslå minimal containment
3. forklar konsekvens
4. vent på Peter før større implementation

## 22. Leverancer

Opret et dokumentationsspor, fx:

`Dokumentation/Assessment_2026-08_Edge_Trust_Service/`

med:

- `00_README.md`
- `01_EXECUTIVE_ASSESSMENT.md`
- `02_IDENTITY_AND_CREDENTIAL_MATRIX.md`
- `03_PROVISIONING_STATE_MACHINE.md`
- `04_RBAC_CAPABILITY_REVIEW.md`
- `05_PKI_AND_CERTIFICATE_LIFECYCLE.md`
- `06_TECHNICIAN_SERVICE_LIFECYCLE.md`
- `07_EDGE_GENERATOR_CONFORMANCE.md`
- `08_LOCAL_SERVICE_GATEWAY_REVIEW.md`
- `09_CURRENT_TARGET_GAP_MATRIX.md`
- `10_PRIORITIZED_ACTION_PLAN.md`
- `11_ADR_RECOMMENDATIONS.md`

Tilføj en handover-entry med scope, branch, commit, dækningsgrad, ikke-testede områder, vigtigste fund og konkrete spørgsmål til Peter/ChatGPT/Claude.

## 23. Definition of Done

Reviewet er færdigt når:

1. Koden er sammenholdt med target-arkitekturen.
2. Alle credentials er inventeret.
3. Alle trust paths er kortlagt.
4. Provisioning lifecycle er modelleret.
5. Technician lifecycle er modelleret.
6. Current/Target gap matrix findes.
7. P0–P3 er prioriteret.
8. ADR-scope er reconcilet.
9. PR #8/#9 er vurderet mod modellen, hvis de fortsat er relevante.
10. Der er ikke foretaget brede implementation changes som del af assessmentet.

## Review outcome

Assessmentet skal gøre det muligt for Peter, ChatGPT og Claude at vælge en kontrolleret implementeringsrækkefølge og derefter acceptere eller justere de tre foreslåede ADR'er, før yderligere større Edge/provisioning/service-funktioner bygges.