# Non-regression gate for GitHub cleanup — 2026-10-10

**Product owner directive:** NO FUNCTIONALITY MAY BE REMOVED. No automatic PR closures, branch deletions, or functional changes without verified preservation.

## Existing authoritative and historical sources
- `Dokumentation/KRAVREGISTER_og_STATUS_v10.md`: historical requirement/status register (July 7; statuses are not current proof).
- `Dokumentation/LEGACY_REQUIREMENT_ID_INVENTORY_2026-09-16_CHATGPT.md`: 82 preserved historical requirement IDs.
- `Dokumentation/UI_USECASE_CATALOG_2026-08-26.md`: granular user-action/UAT baseline.
- `Dokumentation/CAPABILITY_MAP_2026-09-16_CHATGPT.md` (PR #243): 16 Golden Capabilities, intended bridge requirement→capability→usecase→implementation→test→runtime outcome.
- `Dokumentation/PAKKE_SPOR_REGISTER.md`, ADR-003: historical branch reconciliation and anti-loss rules.
- ADR-004: explicit preservation of general-purpose/root recovery shell in development phase.
- Existing GRC remains authority for current requirements/risks/tests/evidence; no competing database.

## Hard gate for each candidate PR or branch
1. Identify every changed or implied capability, including security, recovery, CLI, GUI, LAB, historical usecases and operational behavior.
2. Map each to requirement ID(s), Golden Capability and UI usecase(s) where present. If no match, add a **candidate mapping** without deleting/renaming the original.
3. Capture before-state from known-good version and after-state with reproducible test, including negative/error/recovery scenarios.
4. Check integration against current main, overlapping PRs and the two actual Edges; do not mistake CI for physical acceptance.
5. No feature may be removed or made unreachable, including root recovery shell (ADR-004), unless Peter explicitly changes the product requirement in a separate documented decision.
6. An old implementation may be superseded only when its observable behavior and recovery guarantees remain available and tests prove equivalence.
7. Preserve historical evidence and original IDs; no destructive cleanups of local stashes, worktrees, branches or tags.
8. If equivalence cannot be proven, mark BLOCKED/UNKNOWN, not CLEAN or SUPERSEDED.

## First four PRs — preservation checks
- #257: Golden Edge image must preserve WiFi, GPS/NTP, watchdog, TOTP service, GPIO, app restart, existing captures, device identity, and physical access.
- #163: preserve post-restart stability window, stale handshake sweeper, safe relay defaults and normal capture during updates.
- #246 → #259: preserve HMAC and existing authenticated upload, reverse tunnel, known-host verification, technician access, fail-closed mTLS transition and recoverability. Do not rotate keys or disable old access without verified replacement.
- #159: preserve exact timestamp semantics and historical captures while adding local/UTC/timezone display contract.

## Immediate working queue
- Extract complete 16 Golden Capability definitions from PR #243; enumerate UI usecase IDs and 82 legacy IDs; join to GRC identities when access exists.
- Add per-PR mapping and test evidence for all 17 open PRs.
- Only then start feature-preserving integration on separate branches with automated and physical gates.

**This gate is a documentation-level policy checkpoint, not a claim that all capabilities have been independently tested.**
