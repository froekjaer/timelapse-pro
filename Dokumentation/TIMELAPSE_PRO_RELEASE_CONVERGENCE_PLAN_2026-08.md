# TimeLapse Pro — Release Convergence Plan (August 2026)

**Status:** Proposed execution baseline  
**Formål:** Samle alle tidligere assessments, reviews, ADR-spor og arkitekturinput i én implementerbar plan frem mod en sammenhængende og brugbar Release Candidate.  
**Princip:** Ingen flere brede reviews som standard. Fra dette punkt bruges eksisterende review-evidens til at bygge, integrere, teste og verificere systemet.

---

## 1. Executive decision

TimeLapse Pro går nu fra **assessment/review mode** til **convergence/stabilization mode**.

Den nuværende kodebase indeholder de fleste nødvendige byggesten, men de er udviklet over flere arkitekturgenerationer. Den primære opgave er derfor ikke at tilføje flere features, men at gøre de eksisterende lag konsistente og ende med ét sammenhængende system.

### Midlertidigt feature freeze

Indtil første sammenhængende RC er nået, bør følgende som udgangspunkt ikke udvides med nye større features:

- Bluetooth/local service features
- browserbaseret shell/terminal
- nye auth-varianter
- nye credential-typer uden for canonical lifecycle
- nye generatorfunktioner
- nye AI-autonome handlinger
- nye retention-/deletion flows uden for Explicit Disposition-modellen

Bugfixes, sikkerhedsrettelser og arbejde der bringer implementationen i overensstemmelse med den valgte target-arkitektur er tilladt.

---

## 2. Kilder der konsolideres

Denne plan konsoliderer og erstatter behovet for yderligere brede reviews baseret på blandt andet:

- Uafhængig 3.-parts assessment 2026-07
- Codex Edge Trust & Service conformance assessment 2026-08
- TimeLapse Core Design Principles
- Architecture Governance
- SABSA Architecture / Risk Assessments
- ADR-001 Platform/Payload split
- ADR-002/003 scope-reconciliation
- Edge Reference Architecture v1
- Controlled Local Service Access-sporet
- Evidence Retention / Explicit Disposition-sporet
- Headend/Edge generator reviews
- RBAC / AgentPrincipal / route-auth arbejde
- PKI / local Edge trust arbejde
- HANDOVER_LOG.md
- PR #5, #6, #8, #9, #10 og #11

Når disse kilder er uenige, skal den valgte target-arkitektur og eksplicitte Product Owner-beslutninger være styrende. Uoverensstemmelser skal løses gennem konkrete ADR-/implementeringsbeslutninger, ikke gennem nye generelle assessments.

---

## 3. Locked target model

### 3.1 TimeLapse Pro som platform + payload

**Platformen ejer:**

- device identity
- provisioning/enrollment
- credentials/trust
- RBAC/capabilities/policy
- audit
- configuration
- update/OTA
- telemetry/health
- diagnostics
- local service gateway
- remote support conduit
- storage services
- backup/restore hooks
- HAL
- AI runtime/platform integration

**TimeLapse payload ejer:**

- camera discovery/control
- capture
- camera-specific diagnostics
- live preview
- focus/exposure functions
- image quality analysis
- timelapse generation
- payload-specific AI

### 3.2 Data-retention principle

Projektbilleder og tilhørende projektdata må ikke slettes automatisk på grund af storage pressure, alder, uploadstatus eller ukendt systemtilstand.

Project disposition skal være eksplicit:

`Active → Completed → Keep / Export / Archive / Explicit Delete`

Storage alarms må ikke udløse destruktiv cleanup.

### 3.3 Edge trust model

Én canonical lifecycle authority skal styre:

`prepare → media_written → bootstrap → hardware_verify → enroll → credential → assign → commission → active → rotate/recover → revoke → retire`

Separate trust paths skal eksistere for:

- Device API identity
- Device support/tunnel identity
- Local technician service identity
- Bootstrap identity
- Local TLS identity
- Update/release trust

Credential reuse mellem disse trust paths bør undgås.

### 3.4 Authorization model

Target authorization model:

`Principal + Role + Capability + Tenant + Resource + MFA + Context → Policy Decision → Allow/Deny`

Ad hoc authorization-betingelser i endpoints skal gradvist erstattes af en central policy decision model.

### 3.5 Technician service model

Normal field service skal kunne udføres uden shell.

Normal local service skal gå gennem:

`Local Service Gateway + short-lived EdgeServiceGrant`

Shell/terminal er en engineering/break-glass capability med skærpet kontrol.

---

## 4. Program work packages

### WP-0 — Baseline consolidation

**Mål:** Ét autoritativt arkitektur- og execution-grundlag.

**Opgaver:**

- Reconcile PR #5, #6 og #11 mod main og hinanden.
- Bring de relevante styrende dokumenter ind i én konsistent baseline.
- Luk/arkivér arbejdsordre-only PR #10 efter at assessment-resultatet er sikret i repoet.
- Opdatér HANDOVER_LOG med denne convergence-plan som styrende execution baseline.
- Markér gamle designbeskrivelser som superseded hvor de direkte konflikter med den nye target-model.

**Exit:** Ingen tvivl om hvilke dokumenter/ADR'er der er styrende for implementeringen.

---

### WP-1 — Identity, Enrollment & Credential Lifecycle

**Mål:** Én canonical device/trust lifecycle.

**Opgaver:**

- Implementér canonical provisioning state machine.
- Inventoryér og normalisér credential-typer.
- Definér canonical credential store og migreringsvej væk fra legacy `devices.api_token`-mønstre.
- Adskil API identity, SSH/tunnel identity og technician/service identity.
- Definér key generation ownership.
- Implementér rotation, revocation, replacement og retirement semantics.
- Fail closed ved ukendt identity/credential state.

**Acceptance:**

- Duplicate identity afvises deterministisk.
- Private credentials har klar owner/storage/lifetime.
- Re-enrollment og replacement har dokumenteret recovery path.
- Revoked device kan ikke længere bruge API, tunnel eller service trust path.

---

### WP-2 — Authorization & EdgeServiceGrant

**Mål:** Samlet policy enforcement for Headend og local service.

**Opgaver:**

- Introducér central policy decision abstraction.
- Konsolidér rolle + capability + tenant/resource + MFA/context.
- Introducér short-lived, Edge-bound `EdgeServiceGrant`.
- Stop brug af almindelig Headend-session/JWT som lokal permanent technician credential.
- Gennemgå PKI-, update-, GPIO-, terminal-, preview- og technician-endpoints mod modellen.

**Acceptance:**

- Local technician session kan ikke genbruges mod almindelige Headend-API'er.
- Grant er device-bound, capability-bound og time-bound.
- Revocation/expiry håndhæves.
- Audit indeholder principal, resource, action, decision og reason.

---

### WP-3 — Local Service Gateway

**Mål:** Én service-security boundary på Edge.

**Opgaver:**

- Etabler fælles Local Service Gateway.
- Gør transportlaget uafhængigt: Bluetooth PAN, Wi-Fi, Ethernet og USB networking må bruge samme auth/policy/session/audit-model.
- Split `totp-service.py` funktionelt i gateway/auth/session/policy/audit/api/diagnostics/netværk.
- Behold TOTP som offline/break-glass path, ikke normal identity.
- Gør shell disabled-by-default og særskilt privileged capability.

**Acceptance:**

- Normal service kan udføres uden shell.
- Samme authorization semantics uanset transport.
- Offline recovery er separat og auditeret.
- Session timeout og policy revoke lukker aktiv adgang korrekt.

---

### WP-4 — Generator & Provisioning split

**Mål:** Reproducerbar release + separat device provisioning.

**Target:**

`Generic Signed Edge Image + Signed Device Provisioning Envelope`

**Opgaver:**

- Adskil Release Artifact Builder, Device Provisioning Service, Credential Issuer og Flash Composer.
- Minimer permanente device-private credentials i flash-image.
- Provisioning envelope skal være one-time/limited scope og destrueres/deaktiveres efter successful enrollment.
- Bevar hardware target/HAL profile som deklarativ kontrakt.
- Fjern hardcoded OS catalog assumptions som `ubuntu:24.04` fra production path.

**Acceptance:**

- Samme generiske image kan bruges til flere Edges.
- Per-device binding sker gennem signed provisioning intent.
- Image kan reproduceres og verificeres uafhængigt af kunde/site.
- Enrollment failer lukket ved mismatch.

---

### WP-5 — Commissioning & Technician Experience

**Mål:** Gør en ny Edge mulig at klargøre og idriftsætte uden manuel hacking.

**Implementér:**

- Preparation/preflight workflow
- Bench commissioning
- Site commissioning
- CommissioningReport v1
- ServiceRecord/Service Mission skeleton

**CommissioningReport v1 skal mindst verificere:**

- device identity
- hardware profile
- software release/signature
- customer/site assignment
- camera detect + test capture
- image quality result
- modem/network
- GPS/time
- storage
- relays
- local TLS
- Headend/API connectivity
- service access
- update capability
- technician identity
- deviations

**Resultat:** `PASS`, `PASS WITH DEVIATIONS` eller `FAIL`.

---

### WP-6 — Project Data Lifecycle & Retention

**Mål:** Implementér Core Design Principle om retain-until-explicit-disposition.

**Opgaver:**

- Fjern/disable destructive circular-buffer behavior for project evidence.
- Gør storage thresholds stateful monitoring-only.
- Implementér project completion lifecycle.
- Implementér Keep / Export / Archive / Explicit Delete.
- Export/archive skal have manifest + SHA-256 verification.
- Explicit Delete skal være privileged, reauthenticated, auditeret og adskilt fra export/archive.
- Audit record for deletion bevares.

**Acceptance:**

- Storage pressure alene kan aldrig slette project captures.
- Ukendt upload/archive/checksum state betyder retain.
- Projekt kan afsluttes og bevares read-only.
- Export/archive kan integritetsverificeres.

---

### WP-7 — Headend modular convergence

**Mål:** Reducér risikoen fra monolitisk `headend/main.py` uden big-bang rewrite.

**Opgaver:**

- Ingen nye feature-endpoints direkte i `main.py`.
- Flyt de dele der ændres under WP-1..WP-6 til routers/services med klare contracts.
- Centralisér auth/policy hooks.
- Bevar behavior gennem contract tests.

**Acceptance:**

- Nye integrationsflader lander uden at gøre `main.py` større.
- Route-auth gate er grøn.
- Platform/payload boundaries er tydeligere efter hvert work package.

---

### WP-8 — Backup, Restore, Observability & SIEM

**Mål:** Luk operational readiness-gates.

**Opgaver:**

- Kør evidenseret restore drill for Headend DB og picture store.
- Verificér backup integrity.
- Implementér stateful storage/SIEM alarms med firing/ack/resolved/reminder.
- Bevar logs som standard; komprimer/archive frem for automatisk delete.
- Verificér credential/PKI restore semantics uden at bryde trust model.

**Acceptance:**

- Dokumenteret restore kan gennemføres.
- Persistent alarm skaber ikke mailstorm.
- Recovery efter Headend restart bevarer relevant state.

---

### WP-9 — Release Candidate E2E qualification

**Mål:** Bevæg systemet fra "mange fungerende dele" til "brugbar sammenhængende release".

**Canonical new-Edge test:**

`Build signed image`
→ `Create provisioning envelope`
→ `Flash`
→ `First boot`
→ `Hardware verify`
→ `Enroll`
→ `Issue credentials`
→ `Assign customer/site`
→ `Technician login`
→ `Camera detect`
→ `Test capture`
→ `Image QA`
→ `Network/modem test`
→ `Upload`
→ `CommissioningReport PASS`
→ `Reboot`
→ `Reconnect`
→ `Scheduled capture`
→ `Upload`
→ `Remote diagnostics`

Testen skal gentages på de hardware targets der skal være supported i RC, mindst Orange Pi 4 Pro og Raspberry Pi 4B hvis begge fortsat er i release scope.

---

## 5. Open PR disposition

### PR #5 — Core Design Principles

**Action:** Reconcile og integrér som styrende policy baseline. Konflikten omkring automatic retention skal løses gennem WP-6, ikke ved at afvise princippet.

### PR #6 — Architecture Governance

**Action:** Reconcile og integrér. Brug governance-lifecycle til at markere dokumenter Accepted/Implemented/Verified i takt med convergence-programmet.

### PR #8 — OS catalog refresh

**Action:** Hold implementationen, men fjern hardcoded OS assumptions før production qualification. Merge kun når dens scope er kompatibelt med WP-4.

### PR #9 — Broad Edge/runtime PR

**Action:** Split.

Kan vurderes/cherry-pickes separat:

- camera recovery fix
- gphoto dependency closure
- systemd path permission fix
- importer case-sensitivity fix
- data lifecycle/export fixes efter WP-6 alignment

Hold tilbage indtil WP-2/WP-3:

- browser SSH terminal
- shared break-glass-key based service flow
- normal technician shell exposure

### PR #10 — Work order

**Action:** Assessment-input er leveret. Bevar historik, men den skal ikke være execution authority fremover.

### PR #11 — Edge Reference Architecture

**Action:** Reconcile og brug som target architecture for WP-1..WP-5.

---

## 6. Merge discipline during convergence

- Én work package pr. branch/PR hvor praktisk.
- Hold unrelated fixes ude af samme PR.
- Hver PR skal angive hvilket WP og hvilke acceptance criteria den lukker.
- Runtime PR må ikke samtidig introducere nye ureviewede policyprincipper.
- Security-sensitive changes kræver målrettede tests og negativ-tests.
- Ingen direkte merge af broad PR'er med blandet auth, UI, data lifecycle og runtime scope.

---

## 7. Definition of RC1

TimeLapse Pro kan kaldes første convergence RC når følgende er opfyldt:

- [ ] Styrende baseline er integreret og entydig.
- [ ] Device identity/provisioning lifecycle er canonical og testet.
- [ ] Credential inventory er implementeret/reconcilet.
- [ ] API, SSH/tunnel og technician credentials er separeret.
- [ ] EdgeServiceGrant fungerer.
- [ ] Local Service Gateway håndhæver fælles policy.
- [ ] Normal technician workflow kræver ikke shell.
- [ ] Generator producerer reproducible signed image + provisioning envelope.
- [ ] CommissioningReport PASS kan opnås på fysisk Edge.
- [ ] Capture/upload virker efter reboot.
- [ ] Remote diagnostics virker.
- [ ] Project data slettes ikke automatisk.
- [ ] Complete/Keep/Export/Archive/Delete lifecycle er implementeret eller eksplicit scoped ud af RC med safety-preserving behavior.
- [ ] Restore drill er bestået.
- [ ] Stateful SIEM/storage alarm er implementeret.
- [ ] CI er grøn.
- [ ] Kritiske security findings er lukket eller eksplicit risk-accepted af Product Owner.
- [ ] Release notes, rollback og upgrade path findes.

---

## 8. Roles during convergence

### Product Owner

Træffer endelige produkt- og risikobeslutninger og accepterer irreversible tradeoffs.

### Architecture owner

Holder target-model, contracts, WP-rækkefølge og acceptance criteria sammen. Nye implementationer vurderes mod convergence-planen frem for mod enkeltstående gamle reviews.

### Codex

Primær repository implementation engine:

- kode
- migrations
- refactoring
- tests
- CI
- PR'er
- contract implementation

### Claude

Anvendes selektivt til konkrete runtimefejl, afgrænsede implementationer eller målrettet teknisk assistance. Ikke flere brede reviews medmindre en ny fundamental risikoklasse opstår.

---

## 9. Immediate execution order

1. **WP-0 Baseline consolidation**
2. **WP-1 Identity/Enrollment/Credentials**
3. **WP-2 Authorization + EdgeServiceGrant**
4. **WP-3 Local Service Gateway**
5. **WP-4 Generator split**
6. **WP-5 Commissioning**
7. **WP-6 Data lifecycle**
8. **WP-8 Backup/restore/SIEM**
9. **WP-9 E2E RC qualification**

WP-7 Headend modular convergence sker additivt gennem WP-1..WP-8 og er ikke et separat big-bang rewrite.

---

## 10. First Codex implementation brief

Codex skal efter denne plans accept begynde med **WP-0 + WP-1**.

Første leverance skal være:

1. Reconcile target baseline docs into a single implementation branch without changing runtime behavior.
2. Implement canonical provisioning state machine and credential inventory/schema in a backwards-compatible manner.
3. Add contract tests for allowed/forbidden lifecycle transitions.
4. Add migration/compatibility handling for existing devices.
5. Do not implement browser shell, new Bluetooth functions or new local service features in the same PR.
6. Report exactly which legacy credential paths remain after the increment.

---

## 11. Final principle

> **The review phase is complete enough to build. From this point, progress is measured by coherent contracts, passing end-to-end flows and operational evidence — not by the number of additional assessments produced.**
