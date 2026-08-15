# Codex Build Order — Trust Service, Secure Service DMZ & Release Convergence

**Repository:** `froekjaer/timelapse-pro`  
**Execution authority:** `TIMELAPSE_PRO_RELEASE_CONVERGENCE_PLAN_2026-08.md` + `TIMELAPSE_PRO_LOCKED_ARCHITECTURE_DECISIONS_2026-08.md`  
**Mode:** Implementation/convergence. No broad review phase. No new unrelated features.

## 1. First principle

Implement the locked target architecture. Do not reopen architecture choices already fixed by the Locked Architecture Decisions document unless a genuine contradiction prevents implementation.

If implementation reveals a conflict, prefer the locked target model and adapt legacy code through explicit compatibility/migration paths.

## 2. Repository / PR reconciliation before implementation

Create a clean convergence worktree/branch from the latest intended main baseline and explicitly reconcile the open branches/PRs.

Required disposition:

- PR #13: canonical WP-1 implementation. Preserve and build on it.
- PR #12: convergence documentation source. Its content is absorbed into the implementation baseline; do not duplicate it indefinitely.
- PR #11: preserve Edge Reference Architecture content, replace remaining Proposed/TBD decisions with the locked decisions.
- PR #10: historical work order only; assessment is complete.
- PR #9: do not merge wholesale. Extract only convergence-compatible fixes as focused commits/PRs.
- PR #8: preserve useful update work but remove hardcoded OS assumptions before production merge.
- PR #6: reconcile Architecture Governance into the baseline; no open review questions remain for convergence.
- PR #5: reconcile Core Design Principles; explicit-disposition is decided in favor of retain-until-explicit-disposition.
- PR #4: historical verification only.

Do not discard unique evidence from HANDOVER/assessment documents when closing superseded PRs.

## 3. Complete WP-1 merge readiness

Before WP-2 implementation:

- run CI / full relevant suite on PR #13 branch head
- rehearse migration v29 against a copy of an existing database
- verify rollback instructions
- confirm legacy Device API migration remains idempotent
- confirm no revoked/retired credential becomes active after migration or restore

If clean, make PR #13 ready for merge.

## 4. WP-2 — TimeLapse Trust Service

Create a first-class logical module boundary, initially hosted inside Headend.

Suggested namespace (adapt to repository conventions):

`headend/trust/`

with clear sub-responsibilities such as:

- `identity.py`
- `lifecycle.py`
- `credentials.py`
- `pki.py`
- `policy.py`
- `grants.py`
- `revocation.py`
- `audit.py`
- `models.py`

The exact files are not normative; the boundary is.

### Trust Service authority

It is the sole logical authority for:

- device identity decisions
- enrollment/lifecycle trust decisions
- credential inventory/lifecycle
- PKI issuance policy
- trust anchors
- revocation/rotation metadata
- bootstrap credential issuance
- EdgeServiceGrant issuance
- authorization policy decisions
- trust audit

Do not put CA private keys or trust-authority logic in the DMZ gateway.

### Operational private key rule

- Edge support/tunnel SSH private key: generated/stored on Edge
- Edge local TLS leaf private key: generated/stored on Edge
- Headend stores public key/cert metadata/fingerprint/status/revocation information
- CA/release/update signing keys remain centrally protected

### Policy Decision Point

Implement one central decision abstraction:

`Principal + Role + Capability + Tenant + Resource + MFA + Context -> Allow/Deny + reason`

Compatibility adapters may wrap existing `require_role` and role checks during migration.

Unknown action/resource/context denies by default.

### EdgeServiceGrant

Implement short-lived signed grants that are:

- user/technician-bound
- Edge-bound
- tenant/resource-scoped
- capability-scoped
- MFA-aware
- purpose-bound
- expiring
- replay-protected
- revocable
- auditable

A normal Headend session/JWT must not be accepted as an EdgeServiceGrant and must not be persisted on Edge for later technician access.

### WP-2 contract tests

At minimum:

- grant cannot be used on another Edge
- grant cannot cross tenant/customer boundary
- grant cannot exceed capability scope
- grant expires and is denied
- revoked grant denied
- missing required MFA denied
- normal Headend session token rejected as local service grant
- replayed technician challenge denied
- viewer cannot obtain privileged service grant
- technician without required capability denied
- admin override behavior explicit and audited
- unknown action/resource/context denied
- every decision includes a reason

## 5. Secure Service DMZ foundation

Introduce the DMZ as a logical deployable boundary, initially allowed to coexist on the same host using process/container/firewall segmentation where necessary.

DMZ responsibilities may include:

- Edge API gateway/proxy
- enrollment gateway
- update distribution gateway
- remote-support gateway
- rate limiting
- protocol/schema validation
- request-size controls
- abuse controls
- conduit enforcement

### Hard rules

- DMZ is never the trust authority.
- DMZ cannot issue identity, certificates, grants or trust anchors by itself.
- DMZ has no direct unrestricted database access.
- DMZ has no direct access to CA private keys.
- DMZ-to-Trust/Application calls are allow-listed and service-authenticated.
- Data zone is not directly routable from DMZ.

### Network/config artifact

Create a versioned logical zone/conduit specification describing:

- External -> DMZ
- DMZ -> Trust Service
- DMZ -> Application services
- Trust Service -> data stores it explicitly owns
- Application -> data stores
- prohibited flows

Where practical, express this as testable configuration/contracts, not prose only.

## 6. SSH / support conduit migration

Move target ownership away from Headend-held per-Edge private support keys.

Target:

- Edge generates Ed25519 support key locally
- Headend/Trust Service registers public key + fingerprint + lifecycle state
- host trust explicit/pinned or CA-based
- no AutoAddPolicy in final managed path
- legacy `devices.ssh_private_key` migration adapter only
- shared break-glass key not normal service identity

Do not enable browser SSH terminal as normal technician functionality in this WP.

## 7. Local TLS CSR lifecycle

Target:

1. Edge generates local leaf private key.
2. Edge generates CSR containing expected device/SAN identity.
3. Enrollment/local-PKI request is brokered through DMZ where applicable.
4. Trust Service verifies lifecycle, binding and policy.
5. Edge Local CA signs leaf certificate.
6. Edge receives certificate, never central copy of leaf private key.
7. Trust Service records fingerprint, issuance, expiry, rotation and revocation state.

Keep migration compatibility for existing image-injected keys until WP-4, but new canonical path must be CSR-based.

## 8. WP-3 — Local Service Gateway

After WP-2 acceptance, implement one Local Service Gateway security boundary on Edge.

Common semantics regardless of transport:

- Bluetooth PAN
- Wi-Fi
- Ethernet
- USB networking

Gateway owns local session handling, grant validation, capability enforcement, audit and rate limiting.

TOTP remains offline/break-glass compatibility only.

Normal field service must not require shell.

Shell/terminal is disabled by default and requires explicit engineering/break-glass capability, step-up auth, TTL, purpose and audit.

Refactor `totp-service.py` incrementally behind the gateway; do not perform an uncontrolled rewrite.

## 9. WP-4 — Generator / provisioning split + DMZ production routing

Implement target:

`Generic Signed Edge Image + Signed Device Provisioning Envelope`

Separate logical responsibilities:

- Release Artifact Builder
- Device Provisioning Service
- Credential Issuer
- Flash Composer

Provisioning envelope must be signed, device-bound, purpose-limited, expiring/consumable and unusable after successful enrollment.

Permanent Edge TLS/SSH private keys are generated on Edge, not pre-baked into the generic image.

Remove hardcoded OS catalog assumptions from production paths.

Only switch external Edge/enrollment/update/support traffic to DMZ production conduits after WP-2/WP-3 policy and tests are green.

## 10. Remaining convergence WPs

Continue the existing Release Convergence Plan without reopening scope:

- WP-5 CommissioningReport v1 + technician lifecycle
- WP-6 retain-until-explicit-disposition project lifecycle
- WP-7 incremental Headend modular convergence
- WP-8 restore/backup/SIEM operational readiness
- WP-9 full physical E2E RC qualification

## 11. Required treatment of all historical input

Before declaring convergence complete, maintain a source-to-decision traceability table covering at minimum:

- July independent 3P assessment
- August Edge Trust & Service assessment
- Core Design Principles
- Architecture Governance
- SABSA architecture/risk assessments
- ADR-001/002/003
- Edge Reference Architecture
- RBAC/remote operations design
- Edge generator reviews
- PKI/local trust work
- retention/storage/SIEM findings
- Claude review findings
- Codex assessment findings
- HANDOVER_LOG entries
- Product Owner decisions recorded in Locked Architecture Decisions

Each material finding must be classified as:

- implemented
- accepted risk/deferred beyond RC1 with rationale
- superseded by a locked decision
- not applicable, with rationale

No material finding may remain as an unowned `TBD`, `TODO decision`, `open policy question` or ambiguous Proposed choice at RC1 baseline.

## 12. Merge discipline

- one work package / coherent change set per PR where practical
- no unrelated feature bundles
- every PR states WP, locked decision references and acceptance criteria
- tests and migration/rollback evidence included
- superseded PRs are closed with a comment pointing to the absorbing PR/decision
- documentation and runtime must not describe contradictory authorities

## 13. Final output expected from Codex

For each WP provide:

1. branch + PR
2. acceptance criteria status
3. migrations
4. rollback path
5. tests
6. legacy paths remaining
7. conflicts reconciled
8. historical findings closed/superseded/deferred
9. exact next WP

The goal is not another review. The goal is one coherent, deployable TimeLapse Pro RC1 with no unresolved architecture decisions in its implemented scope.
