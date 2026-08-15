# TimeLapse Pro — Convergence Source-to-Decision Traceability

**Status:** Living RC1 convergence traceability baseline  
**Authority:** `TIMELAPSE_PRO_RELEASE_CONVERGENCE_PLAN_2026-08.md`, `TIMELAPSE_PRO_LOCKED_ARCHITECTURE_DECISIONS_2026-08.md`, `CODEX_BUILD_ORDER_TRUST_DMZ_CONVERGENCE_2026-08.md`  
**Last updated:** 2026-08-15

This file records how historical review inputs and open PRs are treated during convergence. It is not a new review and does not reopen accepted architecture decisions.

## Open PR Disposition

| Source | Material input | Locked disposition | Implementation trace |
| --- | --- | --- | --- |
| PR #5 — Core Design Principles | Platform/payload split, explicit disposition, retention principle | Reconcile and retain. Conflict around automatic retention is resolved in favor of retain-until-explicit-disposition and implemented in WP-6. | WP-6; locked decisions §2, §14, §19 |
| PR #6 — Architecture Governance | Governance lifecycle and document state management | Reconcile into baseline. No open policy questions remain for convergence; use Accepted/Implemented/Verified states as execution tracking. | WP-0/WP-6/WP-8; locked decisions §1, §19 |
| PR #8 — OS catalog refresh | Useful update/catalog work with hardcoded OS assumptions | Preserve useful implementation, but production merge waits for WP-4 removal of hardcoded OS assumptions. | WP-4; build order §9 |
| PR #9 — Broad Edge/runtime PR | Camera recovery, dependency closure, permission fixes, data/export fixes, browser SSH terminal, shared break-glass/service flow | Split. Cherry-pick only convergence-compatible fixes. Hold browser terminal, shared break-glass normal-service and normal technician shell until WP-2/WP-3 policy and gateway are implemented. | WP-2/WP-3/WP-6 split; locked decisions §10, §11, §19 |
| PR #10 — Edge trust/service work order | Historical review brief and assessment input | Superseded as execution authority. Preserve assessment evidence and handover references. | WP-0 evidence; locked decisions §19 |
| PR #11 — Edge Reference Architecture | Proposed Edge reference architecture and ADR proposals | Reconcile useful architecture text into locked baseline. Proposed/TBD wording is superseded by locked decisions. | WP-2/WP-5; locked decisions §3-§13 |
| PR #12 — Release Convergence Plan | Release convergence plan, locked decisions and Codex build order | Merge-ready documentation source. Absorb into implementation baseline; avoid duplicate contradictory authority after PR #13 merges. | WP-0/WP-1/WP-2; PR #13 |
| PR #13 — WP-1 | Canonical Edge lifecycle and credential inventory implementation | Canonical WP-1 implementation. Merge after CI and v29 rehearsal. | `edge_lifecycle_records`, `edge_credential_inventory`, v29 |

## Historical Finding Disposition

| Source group | Finding theme | Classification | Decision / rationale | Implementation trace |
| --- | --- | --- | --- | --- |
| July independent 3P assessment | Need explicit platform architecture, trust boundaries and assurance traceability | Implemented / in progress | Platform/payload split and Trust Service/DMZ boundaries are locked. Traceability is maintained here and in WP handovers. | Locked decisions §2-§4; WP-2 |
| August Edge Trust & Service assessment | Edge identity, credential lifecycle, technician service model and controlled local access were inconsistent | Implemented / in progress | WP-1 implements canonical lifecycle and credential authority. WP-2 implements PDP and EdgeServiceGrant. WP-3 implements Local Service Gateway. | PR #13; WP-2/WP-3 |
| SABSA/risk assessments | Trust decisions and business attributes must map to controls/evidence | Implemented / in progress | Trust decisions centralize in TimeLapse Trust Service. Every PDP decision must return Allow/Deny plus reason. | WP-2 PDP tests |
| ADR-001/002/003 and ADR proposals | Edge identity, service lifecycle and controlled local service access needed accepted ADR direction | Superseded by locked decision until accepted ADRs are finalized | Locked decisions are execution authority. ADR text may be reconciled later without changing implementation semantics. | Locked decisions §5-§12 |
| RBAC / remote operations design | Role checks were endpoint-local and not capability/resource/context based | Implemented in WP-2 | Existing `require_role` becomes compatibility adapter around central PDP. Unknown action/resource/context denies by default. | WP-2 PDP |
| Edge generator reviews | Image generation mixed release artifact, provisioning envelope and credential issuance | Deferred beyond WP-2 | Target is generic signed image plus signed provisioning envelope. Full split is WP-4. | Locked decisions §12; WP-4 |
| PKI/local trust work | Local TLS leaf private keys were centrally generated/injected in legacy flow | Deferred with compatibility | New canonical path is Edge-generated key + CSR signed by Trust Service. Existing image-injected keys are migration compatibility. | WP-2/WP-4 |
| Retention/storage/SIEM findings | Project evidence must not be deleted by pressure, age or unknown state | Deferred to WP-6 | Retain-until-explicit-disposition is locked. Storage alarms are monitoring, not deletion authority. | Locked decisions §14; WP-6 |
| Claude review findings | Hidden config, SFTP known_hosts, OS assumptions, camera/GDPR/data lifecycle issues | Mixed: implemented / deferred | Security-critical compatibility fixes may be cherry-picked. Broad runtime/data lifecycle changes wait for their WP. | PR #9 split; WP-4/WP-6 |
| Codex assessment findings | Edge trust/service conformance gaps | Implemented / in progress | WP-1 closes lifecycle/credential foundation; WP-2 starts Trust Service, PDP, EdgeServiceGrant and Secure Service DMZ foundation. | PR #13; WP-2 |
| HANDOVER_LOG entries | Operational evidence and prior implementation notes | Implemented as evidence source | Do not discard unique evidence when closing superseded PRs. Handover entries remain chronological evidence. | `HANDOVER_LOG.md` |

## PR #9 Split Disposition

| PR #9 slice | Treatment | Target |
| --- | --- | --- |
| Camera recovery fix | Candidate focused cherry-pick if still needed after WP-1/CI baseline | Separate bugfix PR |
| gphoto dependency closure | Candidate focused cherry-pick if tests show gap | Separate dependency PR |
| systemd path permission fix | Candidate focused cherry-pick if compatible with locked service lifecycle | Separate ops PR |
| importer case-sensitivity fix | Candidate focused cherry-pick if still failing | Separate bugfix PR |
| data lifecycle/export fixes | Hold until retain-until-explicit-disposition model is implemented | WP-6 |
| browser SSH terminal | Do not merge as normal service capability | WP-3 after EdgeServiceGrant/Local Service Gateway |
| shared break-glass key service flow | Do not merge as normal technician identity | WP-2/WP-3 controlled break-glass policy |

## No Open Decisions

No material item above remains an unowned `TBD`. Items marked deferred have an owning WP and rationale.
