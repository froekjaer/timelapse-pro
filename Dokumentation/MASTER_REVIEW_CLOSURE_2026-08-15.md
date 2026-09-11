# TimeLapse Pro — Master Review Closure Status — 2026-08-16

**Status:** Authoritative closure ledger  
**Baseline:** `main @ 9b174c0b7ee2df9014e24d179e3721c27a5de9ef`  
**Purpose:** One implementation/closure track for Claude, Kimi, z.ai, Codex and project-owned assessments. This is not a new review.

## 1. Executive state

TimeLapse Pro is in **convergence / finish-and-release mode**. The locked WP-1..WP-4 architecture remains the target. Independent reviews converge on the same conclusion: continue the architecture, close active defects, converge deployed Edges, then execute RC1.

Closure vocabulary is strict:

`OPEN → FIX IN PR → MERGED → VERIFIED → CLOSED`

A review statement or green PR is not closure by itself. `CLOSED` requires the enforcement path to be on `main` with appropriate test or operational evidence.

Current release decision: **not yet approved for unrestricted Internet/customer production**. The remaining blockers are concentrated and understood; no further broad review is required.

## 2. Review evidence now on main

- `Dokumentation/Claude-2026-08-15.md`
- `Dokumentation/Claude_Update_Flow_Review_2026-08-16.md`
- `Dokumentation/kimi-2026-08-15.md`
- `Dokumentation/kimi-update-flow-2026-08-15.md`
- `Dokumentation/z.ai-2026-08-15.md`
- `Dokumentation/z.ai-update-flow-2026-08-16.md`
- Locked architecture decisions, convergence plan, SABSA/ISO/IEC/CRA/GDPR/NIS2 project documentation and WP handovers.

## 3. Verified closures since the reviews

| Closure | Source mapping | Evidence | Status |
|---|---|---|---|
| GDPR/redaction role + tenant isolation, false approval evidence removed | z.ai SEC-ZAI-02 | PR #32 | **CLOSED** |
| Trust grant MFA evidence, Edge/tenant/resource binding and all-capability PDP evaluation | z.ai SEC-ZAI-06/08, false-evidence class | PR #33 + deploy-safe key migration PR #35 | **CLOSED** for reviewed defects; dedicated Trust secret remains preferred operational target |
| Public E2E diagnostics fail closed: no embedded password, no SSH/TLS bypass, no git-pull deployment | z.ai SEC-ZAI-13 | PR #36 | **CLOSED** |
| Real detached OpenPGP release artifact verification on Edge; hash-only/system-hash rejected | Kimi F-005, Claude critical artifact finding, z.ai E-1/SEC-ZAI-10, Kimi UF-01 | PR #41 with real sign/tamper tests | **CLOSED** |
| Integration tests cannot silently target operational Headend | Kimi F-004 | PR #42 | **CLOSED** |
| Headend deployment bound to exact workflow SHA, target UI built first, mandatory health gate + automatic app/UI rollback | Kimi F-003, Claude Headend deploy findings, z.ai D-* | PR #44; main deploy live-verified | **CLOSED / VERIFIED** |
| SFTP host identity always pinned/fail-closed; AutoAddPolicy escape hatch removed | Kimi F-006, z.ai SEC-ZAI-12 | PR #45 | **CLOSED** |
| Unused Headend `passlib` dependency removed | Kimi F-011 partial | PR #46 | **CLOSED partial**; Edge dependency pinning remains open |
| Every executable update alias goes through Edge cryptographic artifact gate | z.ai update E-2 | PR #47 | **CLOSED** |
| Controlled browser SSH terminal restored with MFA/PDP/EdgeServiceGrant/host trust/audit; visible UX restored; legacy trust only migrates on exact key match | Kimi positive addendum + project regression | PR #24/#27/#28 | **CLOSED** |
| Update supersession is already scoped to device + scope_id + test environment | z.ai H-6 | `headend/services/update_supersession.py` current main | **NO ACTION / already constrained** |
| Trust signer has no generic production dev-secret fallback; production/staging fail closed without safe authority | Kimi F-007 | `headend/trust/grants.py` after PR #33/#35 | **CLOSED for reviewed fallback defect** |

## 4. P0/P1 open security closure

These are the remaining security blockers before RC1 release approval.

| ID | Source | Finding | Status / next action |
|---|---|---|---|
| **C-01** | z.ai SEC-ZAI-01 | LAB preview read path uses unsanitized filename / path traversal | **OPEN P0** — sanitize to basename + root confinement on both preview read routes; traversal-negative tests. |
| **C-02** | Kimi F-001 | Headend config merge still supplies shared factory TOTP `JBSWY3DPEHPK3PXP` when no unique service secret exists | **OPEN P1** — stale PR #25 contains intended fix; reapply safely to current `main.py`, fail closed for unprovisioned service access. |
| **C-03** | Kimi F-002 | OS bundle builder shell interpolation + 0777/0666 permissions | **OPEN P1** — remove shell-string composition, validate/allowlist build inputs, least-privilege permissions, negative injection tests. |
| **C-04** | z.ai / Claude | `assign-site` and remaining legacy admin/device secret paths need canonical role + tenant authorization | **OPEN P1** — use existing tenant helpers; negative cross-tenant tests. |
| **C-05** | z.ai | Admin settings may expose secret values | **OPEN P1** — centralized schema-based secret redaction for settings/readback APIs. |
| **C-06** | Claude | Break-glass/audit actor must be bound to authenticated principal, never client supplied | **OPEN P1**. |
| **C-07** | Claude | Edge backup completion filename/path must use canonical sanitization/root confinement | **OPEN P1** — treat as same vulnerability class as C-01. |
| **C-08** | z.ai | Bluetooth/service pairing and local TOTP firewall grants require explicit activation, bounded lifetime and guaranteed cleanup | **OPEN P1**. |
| **C-09** | z.ai | Legacy provision-package may still create operational private keys on Headend | **OPEN P1** — migration-only/retire for new Edge path; preserve WP-4 Edge-owned private keys. |
| **C-10** | z.ai | Session revocation/absolute lifetime gaps in Headend session model | **OPEN P1** — server-side revocation/token-version or equivalent. |

## 5. Update-flow closure after all three dedicated reviews

The three dedicated update reviews are now treated as one deduplicated backlog.

### Closed

- Real cryptographic artifact authenticity: **closed by PR #41**.
- All executable update-type aliases pass the same Edge trust gate: **closed by PR #47**.
- Headend exact-SHA deploy + health rollback: **closed by PR #44**.
- Kimi/Claude/z.ai conclusions that pull model, per-file hashing, offline OS bundle intent and operator UI are useful remain valid, subject to the open items below.

### Open implementation items

| ID | Source mapping | Finding | Closure requirement |
|---|---|---|---|
| **U-01** | z.ai E-3 | Interrupted app install can replace original `prev` rollback source with partially updated state on retry | Persist immutable rollback generation per artifact/update; never overwrite original backup until update reaches terminal success. |
| **U-02** | z.ai E-4 / Claude rollback | No reliable Edge post-restart health/automatic rollback gate for artifact app update | Add postflight liveness/receipt/service health and rollback if new agent fails to become healthy. |
| **U-03** | z.ai E-5 | App file copy is not transaction-like across files | Stage complete tree and atomic/promoted install where feasible; at minimum journal install set + deterministic recovery. |
| **U-04** | z.ai E-6 | App update staging/prev path lacks disk-space preflight | Calculate required staging + rollback space before install and fail before mutation. |
| **U-05** | z.ai E-7 | Pre-update Edge backup upload uses raw `requests.Session()` rather than retry-aware Headend session | Verified current code. Reuse canonical retry session / bounded retry while preserving multipart semantics. |
| **U-06** | Kimi UF-02 | Forced rollback uses shell `cp -r prev/*`, can skip dotfiles and ignores return code | Replace with Python/shutil verified restore and receipt/service verification. |
| **U-07** | Kimi UF-03 | If `deployed` report is lost, same artifact can be installed again next poll | Receipt/artifact-id idempotence guard: re-report terminal state without reinstall. |
| **U-08** | z.ai H-1 | Update report authenticates device but must also prove device is an authorized target before rollup | Apply canonical target/applicability check before accepting report. |
| **U-09** | z.ai H-2 | Customer/site scope applicability must use canonical current tenant/site relationship rather than stale device fields | Reuse central visibility/assignment helper. |
| **U-10** | z.ai H-3 | Policy response needs explicit update↔device environment gate | Enforce environment match or explicit promotion transition. |
| **U-11** | Claude governance bypass / z.ai H-8 | Multiple OS update creation paths encode different review semantics | Choose one canonical authority path; auto-builder must consume the same reviewed state machine. |
| **U-12** | z.ai H-5 | Auto OS bundle must not attribute human approval/signing to first super_admin | Use explicit service principal/system action and preserve later human approval separately. |
| **U-13** | Kimi UF-04 | UI must distinguish OS `blocked/aborted-before-install` from rollback semantics | UI/manual wording. |
| **U-14** | Kimi UF-05 + Claude UI | Update policy needs first-class UI; high blast-radius approval/reject needs proportionate confirmation | Policy editor + target-count/blast-radius preview + clearer error translations. |
| **U-15** | project/z.ai P-01 | Edge `ping()` currently constructs `/api/api/health` when base URL already contains `/api` | Fix canonical health URL and add contract test. |

### Update-flow observations requiring RC evidence, not speculative code now

- **Kimi UF-06:** execute one real signed offline OS bundle install on a test Edge before RC1.
- Restore/update failure semantics must be exercised with power/reboot interruption, not only unit tests.
- Existing Edges must converge to immutable signed artifact installation before they are release evidence.

## 6. Engineering/governance remaining work

- `main.py` remains a monolith; ratchet remains active. New logic should go through routers/services. A few closure fixes still touch legacy routes and should be extracted where practical.
- Test skips/failures must have explicit rationale; no production safety claim may be based solely on source-string tests.
- Edge runtime dependencies still need exact/policy-controlled pinning against a verified baseline; do not guess versions.
- Repository hygiene/publication policy remains open for old runbooks, backups/snapshots and operational details.
- Old PRs #22/#23/#25 and other superseded branches need final disposition once their useful content is reconciled.
- Legacy backup/restore scripts still reference the old `/opt/timelapse` layout while active Mac deployment uses `~/projects/timelapse-pro` and current launchd service naming. Do not patch paths ad hoc: replace/rehearse backup+restore as one current-production contract and record restore evidence.

## 7. Physical / operational release gates

These cannot be truthfully closed by source review alone:

1. Converge both deployed Edges to current signed artifact release path without deleting captures or changing project retention policy.
2. Resolve Edge 2 camera/PTP detection fault physically if remote diagnostics confirm no USB camera.
3. Run blank-media RC commissioning: generic signed image → signed provisioning envelope → Edge-generated keys/CSR → Trust Service enrollment → commissioning → capture → upload → reboot → capture again.
4. Run signed offline OS update E2E on test Edge including failed/postflight rollback scenario.
5. Evidence-backed Headend restore drill covering PostgreSQL, configuration and media store.
6. DPIA/DPA and first-customer legal/compliance gates where applicable.
7. Final external exposure / DNS / TLS / port-8443 decision and mTLS/internal-CA target verification.
8. Confirm no stale production credential such as `TL-DCA63234D813` remains active.

## 8. Non-negotiable project data rule

TimeLapse Pro is a long-duration evidence/timelapse system. **Captures are never automatically deleted to satisfy storage or retention housekeeping.** Project disposition is explicit and human-controlled: archive, export or delete only through a project-close/disposition workflow. Update/backup/restore work must preserve this invariant.

## 9. Execution order from here

1. Close C-01/C-02/C-03 and remaining tenant/secret P1s.
2. Close U-01..U-12 reliability/authority items, with U-13/U-14 as operator UX completion.
3. Rehearse and replace current-production backup/restore contract.
4. Converge both existing Edges onto signed immutable artifacts.
5. Execute physical RC1 gates.
6. Only then change release status from pre-production to RC/pilot.

**No additional broad review is required before executing this list. New review input is accepted only as evidence against this same ledger.**
