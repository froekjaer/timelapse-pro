# GitHub Cleanup and Reconciliation — 2026-10-10

**Status:** Initial inventory and provisional dispositions; no PR merged/closed, no branch deleted, main untouched.

## Verified current PR population

17 open PRs. GitHub metadata at time of review: 7 mergeable=true and 10 mergeable=false; this is NOT technical or governance approval.

| PR | Track | Draft | GitHub mergeable | Preliminary disposition |
|---|---|---|---|---|
| #274 | SSH access design | yes | no | Preserve; requires Peter design decisions; docs-only |
| #259 | mTLS runtime closure | yes | no | Preserve; stacked on #246, cannot merge independently |
| #258 | Apple Foundation Models | yes | no | Preserve; architecture and POC need integration review |
| #257 | Golden Edge builder | no | no | P0; reconcile and perform real image build/hardware test |
| #256 | Edge1 preservation gate | yes | no | Preserve; evidence before re-image |
| #253 | Reverse tunnel health | yes | no | Preserve; verify runtime state and main overlap |
| #250 | Time Machine image load diagnosis | no | yes | Review docs/evidence for merge or archival |
| #248 | GRC consolidation | yes | yes | Preserve; base is claude/security-review-2026-09-19, not main; resolve dependency #247 |
| #246 | Edge API mTLS enrollment | yes | no | Preserve; parent of #259 |
| #245 | Control-plane versus outcome finding | no | yes | Review for evidence retention and governance routing |
| #244 | FF-TLP-0001 SHA documentation | no | yes | Verify referenced SHA and disposition |
| #243 | Capability map | no | yes | Strong candidate for preservation/integration; not authoritative GRC |
| #242 | Physical Edge audit | no | no | Preserve evidence; reconcile later device state |
| #239 | Edge recovery terminal | no | no | Preserve functionality; conflict resolution required |
| #214 | Global Config parallel load | no | yes | Low-risk candidate pending fresh diff/CI |
| #163 | Post-restart health handshake | no | no | Semantic salvage: stability window, stale handshake sweeper, watchdog safety |
| #159 | Capture timestamp display | no | no | Semantic salvage: UTC/local/timezone API and UI contract |

## Historical branch population, not current inventory

2026-09-13 frozen screen: 123 remote branches excluding main; 13 ancestry-merged, 110 not ancestry-merged (51 patch-equivalent/no plus; 59 with plus-marked patches). These numbers are historical, not current. Neither git-cherry nor ancestry alone proves semantic preservation. Source: `Dokumentation/PAKKE_SPOR_REGISTER.md` and linked evidence.

Local work not available from GitHub: 5 historically reported stashes, additional worktrees. Verify read-only on the actual machine; do not pop/drop/delete before preservation and review.

## Non-destructive cleanup workflow

1. Freeze fresh branch/PR snapshot with ref SHA, base SHA, merge base, CI, labels, last activity, file diffs and provenance.
2. Inspect dependency graph and PR-to-PR stacking (#246→#259; security #247→#248).
3. For each PR, compare semantic changes with current main, deployed releases and other active branches.
4. Record one disposition: MERGE_AFTER_TEST, SALVAGE_IN_NEW_PR, SUPERSEDED_WITH_PROOF, KEEP_PENDING_DECISION, or UNKNOWN.
5. Preserve SHA, patch/diff, tests, issue/GRC linkage and explicit rationale before closing any PR.
6. For remote branches without PR, repeat same process, prioritizing unabsorbed patches and active worktrees.
7. Audit local stashes/worktrees with read-only commands, backed up before any cleanup.
8. Only after approval: merge/reimplement, then close/archive; branch deletion requires separate recovery and owner checks.

## Safety and decision gates

- Never auto-delete remote branches, local stashes, worktrees, tags or rollback artifacts.
- No direct merges of stacked PRs without dependency validation.
- No changes to production devices, main or authoritative GRC as part of this inventory.
- Mergeable=true does not imply tests pass or scope is correct.
- All historic findings are revalidated; no closure from comments alone.
- Document evidence per PR: current main SHA, head SHA, diff/patch, conflicts, CI, test output, deployed version, GRC reference, Peter decision where needed.

## Suggested first batch

1. P0 technical reconciliation: #257, #163, #246, #259, #253.
2. Evidence/capability consolidation: #243, #242, #248, #245.
3. Small changes and documentation: #214, #250, #244, #159.
4. Decision-dependent: #274, #258, #256, #239.

This is a provisional triage, not authorization to merge or delete.
