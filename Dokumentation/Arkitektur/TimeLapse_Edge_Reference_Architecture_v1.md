# TimeLapse Pro — Edge Reference Architecture v1

**Status:** Proposed  
**Type:** Normative target/reference architecture  
**Scope:** Edge platform, provisioning, trust, local service and technician lifecycle  
**Repository:** `froekjaer/timelapse-pro`

---

## 1. Purpose

This document defines the target reference architecture for the TimeLapse Pro Edge platform.

It exists to turn the current set of individually useful capabilities into one coherent, testable and governable platform model.

The architecture is driven by the conclusion from the August 2026 Edge Trust & Service assessment:

> TimeLapse Pro has the right building blocks, but does not yet have one canonical lifecycle authority for Edge identity, provisioning, credentials, local service and technician access.

This document is therefore not a description of current implementation. It is the target model against which implementation, pull requests and future ADRs are reviewed.

---

## 2. Relationship to existing architecture

This document does not supersede ADR-001/002/003.

It is intended to sit below the Core Design Principles and Architecture Governance documents, and above implementation contracts.

Conceptually:

```text
Core Design Principles
        |
Architecture Governance
        |
SABSA / Security Architecture
        |
ADR-001 / ADR-002 / ADR-003
        |
Edge Reference Architecture
        |
Provisioning / Credential / Commissioning Contracts
        |
Implementation
```

The reference architecture should be read together with:

- ADR-001 Platform/Payload split
- ADR-002 platform/payload contracts
- ADR-003 reserved runtime enforcement/signing/isolation/control-data-plane scope
- Proposed Core Design Principles
- Proposed Architecture Governance
- Edge Trust & Service assessment

---

## 3. Architectural objective

The TimeLapse Edge shall evolve from a product-specific embedded node into a reusable, security-governed Edge platform hosting one or more payloads.

The platform shall own reusable non-functional capabilities.

The TimeLapse payload shall own camera/timelapse-specific behavior.

A service technician shall experience one coherent service system regardless of whether access uses Bluetooth, Wi-Fi, Ethernet, USB networking or a remote support conduit.

---

## 4. High-level architecture

```text
                         TimeLapse Headend

      +--------------------------------------------------+
      | Identity / Device Registry                       |
      | Provisioning Authority                           |
      | PKI / Trust Services                             |
      | Authorization / Policy Decision                  |
      | Release / Artifact Trust                         |
      | Audit / SIEM / CMDB                              |
      +-----------------------+--------------------------+
                              |
                     Signed Provisioning Intent
                              |
                     Generic Signed Edge Image
                              |
                              v
      +--------------------------------------------------+
      |              TimeLapse Edge Platform             |
      |                                                  |
      | Identity & Enrollment                            |
      | Credential Store                                 |
      | Local Service Gateway                            |
      | Authorization Enforcement                        |
      | Diagnostics                                      |
      | Networking                                       |
      | Update / Rollback                                |
      | Storage                                          |
      | Time                                             |
      | Telemetry / Audit                                |
      | HAL                                              |
      | AI Runtime                                       |
      | Payload Runtime / Loader                         |
      +-----------------------+--------------------------+
                              |
                              v
      +--------------------------------------------------+
      |              TimeLapse Payload                   |
      | Camera                                           |
      | Capture                                          |
      | Preview                                          |
      | Image QA                                         |
      | Timelapse                                        |
      | Camera-specific AI                               |
      +--------------------------------------------------+
```

---

## 5. Core architectural rule: one lifecycle authority

Edge lifecycle state shall not be inferred independently by image builders, bootstrap scripts, API endpoints and local service components.

There shall be one canonical lifecycle model.

Target lifecycle:

```text
manufactured
   |
prepared
   |
media_written
   |
bootstrap_pending
   |
bootstrap_authenticated
   |
hardware_verified
   |
enrolled
   |
credentialed
   |
assigned
   |
active
   +----> degraded
   +----> quarantined
   +----> revoked
   |
retired
```

Each transition shall have:

- explicit trigger
- actor
- preconditions
- required credential
- resulting credentials
- audit event
- retry/recovery path
- forbidden transitions

No implementation component may silently invent a parallel lifecycle.

---

## 6. Identity model

### 6.1 Logical identity

The authoritative Edge identity is Headend-governed.

Hardware attributes such as MAC address, serial number or board identifiers are evidence and binding attributes. They are not by themselves the complete logical identity.

The logical Edge identity should bind:

- Headend device record
- hardware evidence
- device public identity key
- provisioning record
- customer/site assignment
- lifecycle state

### 6.2 Hardware replacement

Physical hardware replacement must not automatically destroy the logical history of the Edge/site/project.

The architecture must distinguish:

- logical Edge identity
- hardware instance identity
- payload/camera identity

This allows controlled replacement while preserving audit history and project continuity.

---

## 7. Credential separation

Different trust paths shall use different credentials.

Minimum target credential classes:

### Bootstrap credential

Purpose: one-time or limited enrollment/bootstrap.

It shall not become the permanent operational API credential.

### Device API identity

Purpose: Edge-to-Headend API access.

It shall be scoped to the device and API audience.

### Support/tunnel identity

Purpose: authenticated support conduit / reverse tunnel.

It shall not reuse the API credential.

### Local service identity

Purpose: technician-to-Edge local management.

Normal access should be personal and short-lived.

### Local TLS server identity

Purpose: authenticate the local Edge service endpoint.

### Release/update trust

Purpose: verify platform/payload artifacts and updates.

### User/technician identity

Purpose: identify the human principal and bind MFA, customer scope and capabilities.

Credential reuse across these trust paths is an architectural exception requiring explicit ADR justification.

---

## 8. Private-key ownership

The target model should minimize private-key distribution.

Where technically possible:

- device operational private keys are generated on-device
- Headend stores public trust material and authorization state
- bootstrap credentials are temporary
- local service grants are short-lived
- release signing keys remain outside Edge runtime

Private keys should not be copied into generic release artifacts.

If a private key must be inserted during provisioning, its purpose, lifetime and destruction/rotation behavior must be explicit.

---

## 9. Generic signed image + provisioning envelope

Release construction and device provisioning are different concerns.

Target split:

```text
Release Artifact Builder
        |
        v
Generic Signed Edge Runtime

Device Provisioning Service
        |
        v
Signed Device Provisioning Envelope

Flash Composer
        |
        v
Install Media
```

The generic image should contain reusable platform software.

The provisioning envelope should contain device-specific intent such as:

- expected logical device ID
- hardware binding evidence
- Headend trust anchor
- bootstrap credential
- provisioning ID
- optional site/customer binding
- approved local service policy

After successful enrollment, bootstrap material should be disabled or destroyed according to policy.

---

## 10. Local Service Gateway

Local service is a platform capability.

There shall be one Local Service Gateway responsible for:

- authentication
- session lifecycle
- authorization enforcement
- capability exposure
- audit
- service API
- transport-independent access

Transport is not the security model.

Supported conduits may include:

- Bluetooth PAN
- Wi-Fi
- Ethernet
- USB networking
- remote support conduit

All transports shall terminate in the same policy and session model.

---

## 11. Technician access model

### 11.1 Normal access

Normal service access should use personal technician identity.

Target flow:

```text
Technician
   |
Headend authentication + MFA
   |
Capability/tenant/resource authorization
   |
Short-lived EdgeServiceGrant
   |
Local Service Gateway
```

An EdgeServiceGrant should be bound to:

- technician identity
- target Edge
- customer/tenant scope
- allowed capabilities
- MFA state
- purpose
- expiry
- nonce/session

It must not be usable as a general Headend session token.

### 11.2 Offline access

Offline recovery is a separate trust path.

It shall be:

- device-specific
- limited
- auditable
- fail-closed
- distinct from normal Headend MFA credentials

Offline access shall not require reuse/caching of a technician's Headend MFA secret.

---

## 12. RBAC + capabilities + context

The target authorization model is not role-only.

Authorization shall evaluate:

```text
Principal
+ Role
+ Capability
+ Tenant/Customer scope
+ Resource ownership
+ MFA state
+ Context
+ Requested action
= Allow / Deny
```

Implementation should converge on a central Policy Decision Point and consistent enforcement points.

Ad hoc endpoint logic such as:

```text
if admin OR super_admin OR on_site_service
```

should be treated as migration debt rather than a long-term authorization model.

---

## 13. Service technician lifecycle

Serviceability is a first-class platform capability.

### Phase 1 — Workshop preparation

The technician should be able to:

- select approved hardware
- select Edge/site/camera intent
- select approved release
- prepare network bootstrap
- prepare provisioning envelope
- write install media
- validate signatures
- perform preflight
- obtain device/service documentation

Target outcome:

`READY FOR BENCH COMMISSIONING`

### Phase 2 — Bench commissioning

A single guided flow should validate:

- hardware identity
- storage
- camera
- modem/network
- GPS/time
- relays/GPIO where relevant
- local service
- local TLS
- mDNS
- Headend reachability
- enrollment
- API identity
- update capability

### Phase 3 — Site commissioning

The workflow shall be optimized for field conditions:

- mobile-first
- poor connectivity
- no internet
- no Headend connectivity
- limited physical access
- minimal manual command-line work

### Phase 4 — Operational maintenance

The technician should diagnose through product/service semantics rather than Linux internals.

### Phase 5 — Remote support

Remote access shall use controlled support conduits, JIT authorization and auditable sessions.

### Phase 6 — Offline/break-glass recovery

Separate and restricted trust path.

### Phase 7 — Replacement

Board, storage, modem and camera replacement must be governed and traceable.

### Phase 8 — Decommission

Credentials are revoked and runtime trust removed while required evidence and audit history are retained.

---

## 14. Shell policy

Normal field service shall not require shell access.

If a routine service task requires `systemctl`, `journalctl`, `iptables`, `nmcli`, `gphoto2` or similar commands, the preferred long-term response is to expose a governed service capability.

Interactive shell may exist as senior-engineering/break-glass functionality, subject to:

- personal identity
- step-up authentication
- explicit purpose
- short TTL
- controlled destination
- host trust validation
- audit/session evidence
- revocation
- central policy

Browser-based terminal functionality is therefore not a normal technician feature by default.

---

## 15. Platform service vs payload service

### Platform service capabilities

Examples:

- identity status
- enrollment status
- certificate status
- network diagnostics
- storage diagnostics
- time status
- update status
- logs
- health
- telemetry
- service access
- support conduit

### TimeLapse payload service capabilities

Examples:

- camera detect
- camera summary
- autofocus
- manual focus drive
- exposure
- preview
- capture test
- image QA

This split shall follow ADR-001.

---

## 16. AI placement

AI is split by purpose.

Reusable AI runtime/provider infrastructure may be platform infrastructure.

Operational AI used for:

- log analysis
- modem diagnostics
- storage anomalies
- certificate/service diagnostics
- commissioning assistance

belongs to the platform domain.

Camera/image interpretation belongs to the TimeLapse payload domain.

Prompts, data access, retention and result ownership follow the calling domain.

AI remains advisory unless a separately governed automation policy authorizes machine action.

---

## 17. Commissioning contract

A successful installation should generate a machine-verifiable `CommissioningReport`.

Minimum evidence:

- logical identity verified
- hardware verified
- customer/site binding
- release/version
- artifact signature
- SBOM reference
- device credentials established
- local TLS valid
- camera detected
- test capture
- image QA
- network/modem status
- GPS/time status
- storage status
- local service tested
- remote connectivity tested where applicable
- update path tested
- technician identity
- timestamp
- deviations

Result states:

- PASS
- PASS WITH DEVIATIONS
- FAIL

A commissioning PASS must not be based only on a UI status indicator.

---

## 18. Service record / service mission

Service visits should produce durable service evidence.

A generic service record should support:

```text
Need
  -> Observation
  -> Evidence
  -> Diagnosis / Hypothesis
  -> Decision
  -> Action
  -> Verification
  -> Outcome
```

This structure is intentionally aligned with Mission Framework semantics and is a candidate source for future Framework Findings.

---

## 19. PKI lifecycle

The local Edge CA direction is valid, but the lifecycle must be governed.

The target model shall define:

- CA initialization ceremony
- CA backup/recovery
- root compromise procedure
- leaf issuance state requirements
- certificate lifetime
- rotation
- revocation
- lost/stolen Edge handling
- replacement hardware
- duplicate identity handling
- decommission
- monitoring for expiry

Certificate issuance shall be tied to accepted Edge lifecycle state.

---

## 20. Support conduit / SSH

SSH is a transport/tool inside support architecture, not the identity model itself.

The target model shall answer explicitly:

- device-side private-key owner
- Headend host trust
- per-device vs shared credentials
- technician accountability
- tunnel scope
- JIT authorization
- customer approval where required
- session evidence
- rotation/revocation

Shared break-glass keys should be treated as migration or emergency mechanisms, not the desired normal state.

---

## 21. Runtime decomposition target

The current local service implementation should converge toward a modular structure rather than one monolithic local TOTP/service process.

Illustrative target:

```text
local_service/
  gateway
  auth/
    online_grant
    offline_recovery
  session
  policy
  audit
  api
  diagnostics
  network

payloads/timelapse/service/
  camera
  preview
  focus
  capture_test
```

This is a target decomposition, not an immediate refactor mandate.

---

## 22. Safety and failure principles

The Edge platform shall favor fail-safe behavior.

Examples:

- unknown credential -> deny
- unknown capability -> deny
- invalid provisioning state -> stop transition
- certificate mismatch -> deny normal access
- failed commissioning evidence -> do not mark PASS
- revoked identity -> quarantine/deny
- missing bootstrap binding -> stop enrollment

Unknown state must not silently widen access.

---

## 23. Observability and audit

The lifecycle authority should emit structured audit events for at least:

- provisioning created
- media written
- bootstrap attempt
- hardware mismatch
- enrollment
- credential issuance
- technician grant issuance
- local service login
- offline recovery use
- support session open/close
- certificate rotation
- credential revocation
- replacement
- commissioning result
- decommission

Audit must identify actor, device, action, result and reason/context where relevant.

---

## 24. Migration strategy

Migration shall be additive and staged.

Recommended order:

1. Establish canonical provisioning state machine.
2. Establish credential inventory and ownership.
3. Define the three missing ADRs.
4. Define EdgeServiceGrant contract.
5. Introduce central authorization decision model for local service.
6. Introduce CommissioningReport v1.
7. Split generic release artifact from device provisioning envelope.
8. Migrate legacy API token storage.
9. Replace shared support credentials with personal/JIT trust.
10. Refactor local service implementation behind stable contracts.

Existing working functionality should not be removed until replacement paths are verified.

---

## 25. ADR boundaries

This reference architecture recommends three separate Proposed ADRs.

### Edge Identity, Enrollment and Credential Lifecycle

Owns:

- logical device identity
- hardware binding
- provisioning lifecycle
- bootstrap credentials
- operational API identity
- device support identity
- credential generation
- rotation
- revocation
- replacement
- retirement

### Edge Service Lifecycle and Technician Experience

Owns:

- preparation
- bench commissioning
- site commissioning
- normal maintenance
- remote support user journey
- offline recovery user journey
- replacement workflow
- decommission workflow
- technician experience principles
- CommissioningReport / ServiceRecord expectations

### Controlled Local Service Access

Owns:

- Local Service Gateway
- local authentication
- EdgeServiceGrant
- physical-presence requirements
- transports/conduits
- local sessions
- authorization enforcement
- break-glass access
- audit requirements

These ADRs must not take over ADR-001/002/003 contract/runtime enforcement scope.

---

## 26. Conformance rule

Future Edge changes should answer four questions:

1. Which lifecycle state does this operate in?
2. Which principal/credential authorizes it?
3. Which platform or payload component owns it?
4. What evidence proves it succeeded safely?

If one of these questions cannot be answered, the design is not yet ready for implementation authority.

---

## 27. Definition of target success

The architecture is considered successfully realized when a new Edge can move from blank media to active field operation and later through maintenance, replacement and retirement using one documented lifecycle, with:

- no ambiguous identity authority
- no credential reuse between unrelated trust paths
- personal technician accountability
- offline recovery without weakening normal security
- transport-independent local service
- machine-verifiable commissioning
- safe update/rollback
- auditable service history
- clean platform/payload boundaries

---

## 28. Status and next decision

This document is **Proposed**.

It should become implementation authority only after:

- review against the August 2026 Edge Trust & Service assessment
- reconciliation with ADR-001/002/003
- acceptance or adjustment of the three recommended ADR scopes
- Product Owner approval

Until then, it is the preferred target architecture for review and design work, not a claim about current runtime behavior.
