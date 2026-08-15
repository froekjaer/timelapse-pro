# TimeLapse Pro — Locked Architecture Decisions (August 2026)

**Status:** Accepted execution decisions for convergence to RC1  
**Authority:** Product Owner decisions + consolidated internal/external reviews + Release Convergence Plan  
**Purpose:** Remove remaining architecture ambiguity before further implementation. These decisions are implementation authority until explicitly superseded by an Accepted ADR.

## 1. No more broad reviews before RC1

TimeLapse Pro is in convergence/stabilization mode. Existing assessments, security reviews, SABSA work, ADR work, Codex/Claude reviews and operational evidence are sufficient to proceed. New broad reviews are not a prerequisite for implementation. Review activity is limited to concrete PR verification, tests and unresolved implementation defects.

## 2. Platform / payload model is locked

TimeLapse Pro is a modular platform with a TimeLapse payload.

Platform owns identity, trust, provisioning, authorization, configuration, OTA/update, telemetry, diagnostics, local service, remote support conduit, storage services, backup/restore hooks, HAL and platform AI runtime.

TimeLapse payload owns camera discovery/control, capture, preview, focus/exposure, image-quality analysis, timelapse generation and payload-specific AI.

## 3. TimeLapse Trust Service is a first-class platform module

A logical module named **TimeLapse Trust Service** is the sole authority for:

- device identity authority
- enrollment and lifecycle trust decisions
- credential inventory and credential lifecycle metadata
- PKI / CA policy
- trust anchors
- certificate issuance policy
- revocation and rotation metadata
- bootstrap credentials
- EdgeServiceGrant issuance
- authorization policy decisions / capability evaluation
- trust-related audit records

### Deployment decision

For RC1, TimeLapse Trust Service runs inside the Headend deployment but MUST have a stable internal API/module boundary and independent data ownership so it can later be deployed on a separate server/security zone without changing platform semantics.

### Private-key rule

The Trust Service owns trust and issuance authority, not every operational private key.

Operational private keys SHOULD be generated and retained by the component that uses them:

- Edge support/tunnel SSH private key: generated and stored on Edge
- Edge local TLS leaf private key: generated and stored on Edge
- session keys/runtime ephemeral keys: generated where used

Headend/Trust Service stores public keys, certificate metadata, fingerprints, lifecycle state, policy and revocation information.

Trust anchors, CA signing keys, release/update signing keys and bootstrap issuance keys remain centrally controlled by the Trust Service/Headend security boundary.

## 4. Secure Service DMZ is part of the target architecture

TimeLapse Pro SHALL introduce a logical **Secure Service DMZ** between untrusted/external networks and internal trust/application/data zones.

### DMZ purpose

The DMZ terminates or brokers externally reachable service traffic. It is NOT a trust authority.

DMZ functions may include:

- Edge API gateway / protocol proxy
- enrollment gateway
- update distribution gateway
- remote-support gateway
- rate limiting
- WAF/protocol validation
- request size and abuse controls
- conduit enforcement

### Non-negotiable rule

> Internet-facing gateways may never themselves be trust authorities.

The DMZ cannot independently issue device identities, certificates, service grants, authorization decisions or trust anchors.

### Zone model

1. External / Internet / Edge networks
2. Secure Service DMZ
3. Trust / Control zone — TimeLapse Trust Service
4. Application zone — Headend API/UI, CMDB, project management, SIEM/operations
5. Data zone — PostgreSQL, capture storage, backup/archive, audit evidence

DMZ-to-internal communication is explicit, allow-listed and service-to-service authenticated. The DMZ must not have direct unrestricted access to PostgreSQL, capture storage or CA private keys.

For RC1 the zones may be logical/process/container/firewall boundaries on the same physical Headend host where required, but contracts and network policy MUST allow later physical separation without semantic redesign.

## 5. Edge identity lifecycle is centrally governed

The canonical Edge lifecycle authority is Headend/Trust Service governed:

`prepared → media_written → bootstrap_pending → hardware_verified → enrolled → credentialed → assigned → commissioned → active → degraded/quarantined → revoked → retired`

Hardware identity (MAC, serial, board data) is evidence/binding, not the sole logical identity authority.

Unknown lifecycle/credential state fails closed.

## 6. Device API credential authority

`edge_credential_inventory` is the canonical runtime authority for Device API credentials.

`devices.api_token` is legacy migration compatibility only and MUST NOT be the creation path for new Edges.

Credentials have explicit scope, status, issuance, rotation, revocation and retirement state.

## 7. SSH / remote-support identity

The Edge owns its permanent support/tunnel SSH private key.

- key is generated locally on Edge
- Headend stores public key/fingerprint/trust/lifecycle metadata
- `devices.ssh_private_key` is legacy migration compatibility and must be retired
- shared break-glass keys are not normal technician/service identity
- host trust must be explicit; `AutoAddPolicy` is not acceptable for the final controlled support path

Remote support is a controlled conduit, not a general-purpose permanent administration channel.

## 8. Local TLS / PKI lifecycle

Edge generates its local TLS leaf private key and CSR locally.

TimeLapse Trust Service / Edge Local CA validates lifecycle/policy and signs the CSR.

Headend stores certificate/public metadata, fingerprint, expiry, issuance and revocation history — not the Edge leaf private key.

Permanent TLS leaf private keys SHALL NOT be embedded in the final generic image or long-lived provisioning envelope.

Legacy image-injected leaf keys may be migrated during WP-4.

## 9. Authorization model

The target authorization decision is:

`Principal + Role + Capability + Tenant + Resource + MFA + Context → Policy Decision → Allow/Deny + reason`

Authorization logic must converge on a central Policy Decision Point within TimeLapse Trust Service.

Existing `require_role` and endpoint-specific checks are compatibility adapters during migration, not the target authority.

Deny-by-default applies to unknown action/resource/context.

## 10. EdgeServiceGrant is the normal technician authorization token

Normal local/remote technician service uses a short-lived **EdgeServiceGrant** issued by TimeLapse Trust Service.

The grant is:

- technician/user bound
- Edge bound
- tenant/resource scoped
- capability scoped
- MFA-state aware
- purpose bound
- short-lived
- replay protected
- auditable
- revocable

A normal Headend login/session token must not become the persistent local Edge credential and must not be stored on Edge for later technician access.

## 11. Controlled Local Service Access

One **Local Service Gateway** is the security boundary for normal local Edge service.

Bluetooth PAN, Wi-Fi, Ethernet and USB networking are transports/conduits, not separate authorization systems.

Normal technician work MUST be achievable without shell access.

TOTP remains an offline/break-glass compatibility path until replaced by a controlled offline grant mechanism; it is not normal technician identity.

Shell/terminal is a senior engineering/break-glass capability only, disabled by default, step-up protected, time-bound and audited.

Browser SSH terminal functionality from legacy/open PR work MUST NOT be merged as normal service capability before this policy is implemented.

## 12. Generator / provisioning model

Target model is:

`Generic Signed Edge Image + Signed Device Provisioning Envelope`

Release Artifact Builder, Device Provisioning Service, Credential Issuer and Flash Composer are separate logical responsibilities.

The same signed generic image should serve multiple Edges where hardware target permits.

Provisioning envelope is device-specific, signed, limited-purpose, expiry/consumption controlled and invalid after successful enrollment.

Permanent operational private keys should not be pre-baked into generic images.

## 13. Technician lifecycle is a first-class platform capability

Serviceability is part of platform architecture.

Supported lifecycle:

1. workshop preparation
2. bench commissioning
3. site commissioning
4. operational maintenance
5. remote support
6. offline/break-glass recovery
7. hardware replacement
8. decommissioning

CommissioningReport v1 and persistent ServiceRecord/Service Mission are required convergence outputs.

## 14. Project evidence retention is locked

Project images and associated project evidence SHALL NOT be automatically deleted because of storage pressure, age, upload state or unknown system state.

Project lifecycle:

`Active → Completed → Keep / Export / Archive / Explicit Delete`

Export/archive do not automatically delete originals.

Explicit deletion is privileged, reauthenticated and audited.

Unknown upload/archive/checksum state means RETAIN.

Storage alarms are monitoring/capacity controls, not destructive cleanup triggers.

Logs should be retained by default and compressed/archived rather than automatically destroyed, subject to explicit retention policy for non-project operational data.

## 15. AI role

AI runtime is a platform capability; payload-specific AI may extend it.

AI may observe, classify, diagnose and recommend. AI does not autonomously perform irreversible actions such as project deletion, trust changes, credential issuance, security-policy override or destructive camera/data operations without explicitly delegated and policy-controlled authority.

## 16. Headend modular convergence

No new broad feature endpoints should be added directly to monolithic `headend/main.py` where a service/router boundary exists.

Code touched by convergence WPs should move toward services/routers/contracts incrementally. No big-bang rewrite is required before RC1.

TimeLapse Trust Service must have its own namespace/module boundary from the start even while hosted inside Headend.

## 17. Secure zone/conduit principles

- External traffic terminates/brokers through controlled gateways.
- Trust decisions occur behind the DMZ.
- Trust Service has no direct unnecessary Internet exposure.
- Data zone is not directly routable from DMZ.
- Service-to-service calls are authenticated and least privilege.
- Separate API, support/tunnel and technician trust paths remain separate.
- Revocation must terminate relevant access paths.

## 18. Backup / restore / trust recovery

RC1 requires evidence-backed restore of Headend DB and capture store.

Trust Service backup/restore must preserve lifecycle and credential metadata without restoring revoked credentials to active state.

CA/trust-anchor backup is separately protected. Edge private operational keys are not expected to be centrally recoverable by default; replacement/re-enrollment is preferred to mass private-key escrow.

## 19. Open PR disposition is decided

### PR #13 — WP-1

Keep as the canonical WP-1 implementation PR. Merge after CI/full relevant tests and migration rehearsal on an existing DB copy.

### PR #12 — Release Convergence Plan

Content is already included in PR #13 baseline. After #13 merge, close #12 as superseded/absorbed unless a clean documentation-only merge is needed first.

### PR #11 — Edge Reference Architecture

Reconcile into the locked baseline. Preserve useful architecture text, but decisions in this document override any remaining Proposed/TBD wording.

### PR #10 — Codex review work order

Historical input only. Assessment was completed. Close as superseded after handover evidence is retained.

### PR #9 — Broad legacy runtime PR

Do not merge wholesale. Split/cherry-pick only convergence-compatible bug fixes. Hold/reject browser terminal/shared break-glass normal-service functionality until WP-2/WP-3 implementation exists.

### PR #8 — OS catalog refresh

Preserve useful update work, but reconcile with WP-4 and remove hardcoded OS assumptions before production merge.

### PR #6 — Architecture Governance

Reconcile and integrate into the documentation baseline. Any open review questions are resolved by this Locked Decisions document and the Release Convergence Plan.

### PR #5 — Core Design Principles

Reconcile and integrate. Explicit-disposition conflict is resolved in favor of retain-until-explicit-disposition and will be implemented by WP-6.

### PR #4 — Headend generator verification

Historical verification input. Preserve material evidence in handover/history, then close as superseded by the convergence baseline.

## 20. Remaining implementation sequence

1. Complete/merge WP-1 (#13)
2. WP-2 — TimeLapse Trust Service boundary + central Policy Decision Point + EdgeServiceGrant
3. WP-3 — Local Service Gateway and controlled technician access
4. WP-4 — Secure Service DMZ + generator/provisioning split + CSR migration
5. WP-5 — Commissioning and technician experience
6. WP-6 — project evidence retention/disposition
7. WP-7 — Headend modular convergence while touching affected paths
8. WP-8 — backup/restore, observability and SIEM readiness
9. WP-9 — end-to-end RC qualification

Secure Service DMZ implementation may begin structurally during WP-2, but externally routed traffic is not switched to it until its policy and tests are complete.

## 21. Definition of no unresolved architecture decisions

For convergence purposes, an architecture decision is considered unresolved only if implementation cannot proceed without Product Owner choice.

The decisions required for WP-1 through WP-9 are fixed by this document. Implementation discoveries should be resolved within these principles. Only genuine business trade-offs that contradict or materially extend this baseline require a new Product Owner decision.
