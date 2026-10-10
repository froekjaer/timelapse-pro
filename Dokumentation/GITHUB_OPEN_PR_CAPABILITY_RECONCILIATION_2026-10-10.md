# Open PR to capability reconciliation — 2026-10-10

**Status:** All 17 open PR diffs inspected for changed-file scope and preliminary semantic intent. Mapping is candidate-level, NOT proof of uniqueness relative to current main or physical deployment. No merge/close/delete.

## Preservation baseline
- 82 legacy requirement IDs: `LEGACY_REQUIREMENT_ID_INVENTORY_2026-09-16_CHATGPT.md`.
- Granular UI UAT: `UI_USECASE_CATALOG_2026-08-26.md`.
- 16 Golden Capabilities: `CAPABILITY_MAP_2026-09-16_CHATGPT.md` in PR #243.
- GRC is authoritative for tests/risks/evidence; historic statuses are not current proof.
- ADR-004 explicitly protects development/recovery general-purpose shell.

## All 17 open PRs

| PR | Diff files | Candidate functional delta to preserve | Candidate requirements / usecases | Verdict |
|---|---:|---|---|---|
| #274 | 3 | SSH access architecture proposal; MFA service grant, port policy, revocation; requires product decision | CFG-005, CFG-008, SEC-004, SEC-008; UC-TECH / access | KEEP_DECISION_PENDING |
| #259 | 35 | mTLS runtime closure, key/tunnel transition and enforcement; stacked on #246 | SEC-006, SEC-009, PROV-003, CFG-005 | STACKED_RECONCILE |
| #258 | 35 | Apple FM provider, AI router, provider policy, provenance, benchmark, UI | CAP-005, CAP-004, ADM-004; AI UI flows | PRESERVE_CODE_AND_TESTS |
| #257 | 14 | Golden Edge build baseline, WiFi/NTP/watchdog/TOTP/GPIO/image reproducibility | ADM-009, PROV-001/002/006/007/009, CAP-010, CFG-007 | P0_BUILD_AND_HARDWARE_GATE |
| #256 | 3 | Edge1 reimage/preservation gate; operational state protection | PROV-005, ADM-009, CAP-001/002 | PRESERVE_RUNBOOK |
| #253 | 12 | Reverse tunnel health, CLI/bootstrap/Edge agent, SSH UI status | CFG-005, CFG-008, CFG-009, SEC-004 | PRESERVE_RUNTIME_DELTA |
| #250 | 1 | Time Machine/image-load diagnosis and recovery history | PROV-004/005, CAP-003 | PRESERVE_EVIDENCE |
| #248 | 3 | GRC reviewed requirements import and consolidated reporting, 121 reviewed product requirements; stacked on #247 | ADM-004/011, SEC-001, SEC-012 | PRESERVE_GRC_IMPORT; DEPENDENCY |
| #246 | 26 | Edge API mTLS enrollment foundation, Headend/Edge clients, tunnel daemon, CA helper | SEC-006/009, PROV-003, CFG-005 | P0_DEPENDENCY_ROOT |
| #245 | 1 | Control-plane success versus runtime-outcome evidence finding | ADM-004, UPD-012/013, SEC-003 | PRESERVE_FINDING |
| #244 | 1 | FF-TLP-0001 evidence tied to SHA | SEC-003, ADM-004 | PRESERVE_PROVENANCE |
| #243 | 36 | 16 Golden Capabilities; 82 legacy IDs; archaeology inventories and history | ALL CAPABILITIES; ALL LEGACY REQUIREMENTS | PRESERVE_HISTORY; NO LOSS |
| #242 | 2 | Physical Edge audit evidence and device state | CAP-001/002, CFG-007, PROV-001, SEC-003 | PRESERVE_EVIDENCE |
| #239 | 10 | xterm browser recovery shell, edge terminal and regression tests | CFG-008/009, SEC-004; ADR-004 | PROTECTED_RECOVERY_CAPABILITY |
| #214 | 1 | Parallel loading on Global Config UI | ADM-005, CFG-001/002/003 | REVIEW_SMALL_DIFF |
| #163 | 8 | Post-restart health stability window, stale install sweeper, watchdog relay safety | UPD-009/012/015, CAP-001/010, PROV-005 | P0_SEMANTIC_SALVAGE |
| #159 | 9 | Capture timestamp contract, local/UTC/timezone UI and tests | UI-007, CAP-001/009, CFG-007 | SEMANTIC_SALVAGE |

## Critical collisions and dependencies
- #246→#259: parent/child mTLS stack. Compare child to parent head, not only main.
- #247→#248: GRC stack; #248 targets non-main security branch; dependency must be assessed even if #247 is no longer open.
- #239 ↔ #274 ↔ #253 ↔ #246/#259: access paths, tunnel behavior, web terminal, recovery. No migration may strand Edge1/Edge2.
- #257 ↔ #163: clean Edge baseline versus watchdog/update rollback; must pass together.
- #243 ↔ #248: capability/usecase and GRC models should be linked, not duplicated.
- #159 ↔ CAP-03: timestamp semantics must be preserved across capture, API, UI and historical data.
- #258 ↔ Edge NPU shadow: provider policy must not silently change which analysis is authoritative.

## Definition of preservation-complete per PR
- Identify exact unique hunks/behavior not present in main, including equivalent implementation on another branch.
- Map to stable requirement/usecase/capability IDs, add candidate IDs if none exist.
- Record base/head/main SHAs, CI, tests, deployed versions, evidence and conflicts.
- Execute regression test plus relevant runtime/hardware acceptance.
- Document final integration destination and resulting commit SHA.
- Only after independent verification and owner sign-off may PR be closed as integrated/superseded. Never delete branch or local work solely because PR was closed.

## Next engineering batch
1. Current-main semantic comparison of #257 and #163 (including tests and systemd/service side effects).
2. Current-main semantic comparison of #239, #253 and mTLS stack, preserving all remote/recovery paths.
3. Current-main semantic comparison of #159, #214 and #258.
4. GRC and historical artifacts reconciliation (#243/#248 and documentary PRs).
5. Branches without PR and local stashes/worktrees separately.

**Not yet done:** full code-level semantic equivalence, CI execution, local stashes/worktrees inspection, live Edge verification, GRC mutation, merges or PR closures.
