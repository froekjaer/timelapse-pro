# Proposed ADR Outlines — Edge Trust & Service

**Status:** Proposed outlines only  
**Purpose:** Scope reconciliation before individual ADRs are accepted or implemented.

These outlines derive from the August 2026 Edge Trust & Service assessment and the proposed `TimeLapse_Edge_Reference_Architecture_v1.md`.

They do not supersede ADR-001/002/003.

---

# ADR Proposal A — Edge Identity, Enrollment and Credential Lifecycle

## Context

The current Edge implementation contains several overlapping identity and credential mechanisms, including MAC-derived device identity, bootstrap tokens, device API tokens, SSH identities, reverse-tunnel credentials, local TLS certificates and local service credentials.

The system needs one canonical lifecycle authority so that identity, provisioning and credential state are not independently inferred by the image builder, bootstrap code, Headend APIs and local service components.

## Proposed decision

Adopt a canonical Edge identity and credential lifecycle controlled by Headend governance and enforced through explicit lifecycle states.

The logical Edge identity is Headend-governed and bound to hardware evidence and device keys.

Hardware identifiers such as MAC addresses are binding evidence, not the entire logical identity.

Credentials are separated by trust path and purpose.

## Proposed ownership

This ADR owns:

- logical Edge identity
- hardware binding
- provisioning state machine
- bootstrap credential lifecycle
- device API identity
- device support/tunnel identity
- credential generation ownership
- credential storage requirements
- rotation
- revocation
- quarantine
- hardware replacement
- retirement

## Proposed non-ownership

This ADR does not own:

- platform/payload interface semantics from ADR-001/002
- runtime sandbox/signing/control-data-plane mechanics reserved to ADR-003
- detailed local technician UX
- transport-specific Local Service Gateway behavior

## Proposed normative principles

1. One canonical lifecycle authority.
2. Device operational private keys should be generated on-device where practical.
3. Bootstrap credentials are temporary and must not become permanent operational identities.
4. API, tunnel, local service, TLS and release trust credentials must not be reused interchangeably.
5. Credential issuance requires valid lifecycle state.
6. Rotation and revocation are first-class lifecycle operations.
7. Hardware replacement must preserve logical project/service history through governed reassignment.
8. Duplicate or conflicting identity evidence fails closed.
9. All lifecycle transitions are auditable.

## Decisions still required

- Exact canonical state names and transition table.
- API token vs device certificate target for Edge-to-Headend authentication.
- Device-side SSH private-key ownership and migration from legacy models.
- Revocation mechanism for local Edge TLS certificates.
- Recovery model for lost/stolen/replaced hardware.

---

# ADR Proposal B — Edge Service Lifecycle and Technician Experience

## Context

Service functionality currently spans image generation, bootstrap, Bluetooth/Wi-Fi/Ethernet access, local HTTPS, TOTP, technician QR auth, camera tools, diagnostics, remote SSH and break-glass mechanisms.

The technician needs one coherent service experience across preparation, installation, maintenance, recovery and retirement.

Serviceability must be treated as a platform capability rather than an accumulation of scripts and transport-specific tools.

## Proposed decision

Adopt a governed Edge Service Lifecycle with the following phases:

1. Workshop preparation
2. Bench commissioning
3. Site commissioning
4. Operational maintenance
5. Remote support
6. Offline/break-glass recovery
7. Hardware replacement
8. Decommission

Each phase must have explicit preconditions, technician-facing workflow, evidence and completion criteria.

## Proposed ownership

This ADR owns:

- technician service journey
- preparation/preflight expectations
- commissioning workflow
- field/mobile service principles
- normal maintenance experience
- remote-support user journey
- offline recovery user journey
- hardware replacement service flow
- decommission service flow
- CommissioningReport expectations
- ServiceRecord/ServiceMission expectations
- shell-as-break-glass principle

## Proposed non-ownership

This ADR does not own:

- device credential cryptography
- detailed Local Service Gateway authentication protocol
- transport implementation
- ADR-001/002/003 contract/runtime mechanics

## Proposed normative principles

1. Serviceability is a first-class platform capability.
2. Normal field service shall not require shell access.
3. Service workflows shall be mobile-first and usable under poor or absent connectivity.
4. Routine operations shall be exposed as governed service capabilities rather than Linux commands.
5. Commissioning shall produce machine-verifiable evidence.
6. Service actions shall record actor, reason, action and outcome.
7. Diagnostics precede corrective action where practical.
8. Critical changes require rollback/recovery behavior.
9. Hardware replacement shall preserve logical history.
10. AI may assist diagnosis, but remains advisory unless a separately governed automation policy applies.

## Decisions still required

- CommissioningReport v1 schema.
- Required PASS/PASS WITH DEVIATIONS/FAIL gates.
- Minimum offline recovery capabilities.
- ServiceRecord persistence and Mission Framework mapping.
- Which service capabilities belong to platform vs TimeLapse payload.

---

# ADR Proposal C — Controlled Local Service Access

## Context

The Edge can be reached locally through multiple transports and currently contains several authentication/session mechanisms.

Bluetooth, Wi-Fi, Ethernet and USB networking are conduits, not separate security models.

Normal technician identity, offline recovery and senior-engineering break-glass access require distinct trust paths.

## Proposed decision

Introduce one Local Service Gateway as the common authentication, authorization, session, capability and audit boundary for local Edge management.

Normal online/local access uses personal technician identity and a short-lived EdgeServiceGrant issued by Headend after authentication, MFA and authorization.

Offline recovery remains a separate device-specific, restricted and auditable trust path.

## Proposed ownership

This ADR owns:

- Local Service Gateway
- technician local authentication flow
- EdgeServiceGrant concept
- physical-presence requirements where applicable
- transport-independent session model
- capability enforcement for local service
- offline recovery access
- break-glass access requirements
- local service audit
- local-service transport/conduit classification

## Proposed non-ownership

This ADR does not own:

- permanent device identity lifecycle
- release signing/sandbox mechanisms
- detailed payload contracts
- general Headend RBAC architecture outside local service scope

## Proposed normative principles

1. One Local Service Gateway; multiple transports.
2. Transport does not determine authorization.
3. Normal service uses personal identity and MFA according to policy.
4. Headend general session tokens must not become persistent Edge local credentials.
5. EdgeServiceGrant is short-lived, Edge-bound, capability-scoped and audience-restricted.
6. Offline recovery uses a distinct device-specific credential/trust path.
7. Unknown capability or invalid context fails closed.
8. Shell/terminal access is break-glass/senior-engineering by default, not normal technician service.
9. Break-glass sessions require elevated authorization, explicit purpose, TTL and audit.
10. Host/destination trust must be explicit for SSH/support conduits.

## Decisions still required

- EdgeServiceGrant encoding and validation method.
- Physical-presence trigger requirements.
- Offline credential form and recovery lifecycle.
- Session persistence/restart behavior.
- Capability naming/versioning.
- Relationship between local service authorization and central Policy Decision Point.
- Audit/session-recording requirements for browser terminal and SSH.

---

# Proposed dependency order

The ADRs are separate but should be decided in this order:

```text
A. Edge Identity, Enrollment and Credential Lifecycle
            |
            v
C. Controlled Local Service Access
            |
            v
B. Edge Service Lifecycle and Technician Experience
```

Rationale:

- Identity defines who/what is trusted.
- Controlled Local Service Access defines how that trust is enforced locally.
- Technician Experience defines the service journey built on those guarantees.

The three ADRs should be reconciled with the Edge Reference Architecture and assessment before implementation authority is granted.
