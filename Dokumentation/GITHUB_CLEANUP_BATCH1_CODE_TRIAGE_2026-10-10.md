# GitHub cleanup — Batch 1 code-diff triage (2026-10-10)

**Scope:** Read-only inspection of actual unified diffs for PRs #257, #163, #246 and #259. **No merges, closures, deletions, CI execution or live deployment.**

## PR #257 — Golden Edge builder
- Diff: 14 files, ~55,820 characters, 762 added / 5 removed diff lines.
- New/changed: `headend/tools/golden_edge_baseline.py`, `headend/tools/build_edge_disk_image.py`, `headend/tools/inject_edge_image.py`, `headend/tools/Dockerfile.edge`, Orange Pi target, Edge requirements, GPIO udev, sudoers, watchdog unit, tests.
- Preservable functionality: fail-build gate based on actual built image contents, required dependencies and system units; missing WiFi/NTP/watchdog/TOTP/GPIO/service restart packaging.
- Important limitation from PR: actual `docker buildx build` not run. Physical clean-image acceptance remains unverified.
- **Disposition: SALVAGE/RECONCILE, P0.** Do not merge blind; inspect current-main equivalents and image-build compatibility first.

## PR #163 — post-restart health handshake
- Diff: 8 files, ~29,192 characters, 406 added / 29 removed diff lines.
- Changes: `edge/update_lifecycle.py`, `edge/agent.py`, `edge/scripts/watchdog.sh`, `headend/services/post_restart_health.py`, `headend/main.py`, tests.
- Distinct intent: sustained health stability window (PR documents 600s default); timeout sweeper for stale installing targets; safe camera/modem relay behavior on watchdog restart.
- Historical package register dated 2026-09-13 found semantic gaps in main; **this historical finding requires fresh current-main recheck**.
- **Disposition: SEMANTIC SALVAGE, P0.** Port features to current architecture with regression tests; do not resolve conflicts mechanically.

## PR #246 — Edge API mTLS foundation
- Diff: 26 files, ~131,650 characters, 2,386 added / 7 removed diff lines.
- Touches dedicated tunnel sshd, macOS keychain CA helper, Edge mTLS, Headend API, client transport and auth tests.
- Physical pre-login System Keychain probe is documented in PR; this is not a production CA/enrollment proof.
- **Disposition: DEPENDENCY ROOT, P0 security.** Reconcile target ports and current live identity before integration.

## PR #259 — mTLS runtime/security closure
- Diff: 35 files, ~194,289 characters, 3,249 added / 28 removed diff lines.
- Substantial file overlap with #246; PR explicitly states it is stacked on #246, not independent.
- October 1 handover notes tunnel ingress 22022 -> 9222 with temporary dual-port operation, Edge cutover still pending at that time.
- **Disposition: STACKED CHILD, P0 security.** Do not merge directly; evaluate delta relative to #246 rather than diff against main, then confirm latest live port/identity status.

## Cross-PR integration gates
1. Freeze current main/head SHAs, retrieve CI/check status, and compare each changed file to current main.
2. Inspect dependencies and intermediate PRs (including #247/#248 and #268) to avoid double application or wrong base.
3. Build new Golden Edge image and verify on non-production hardware before any re-image.
4. Preserve update rollback and post-restart stability while reconciling mTLS and tunnel changes.
5. Verify physical Edge1/Edge2 state before retiring 22022, rotating host keys or changing access paths.
6. No PR closure or branch deletion without a recorded semantic preservation verdict.

**Evidence status:** Actual PR diffs inspected; no local tests or runtime tests performed. PR metadata alone cannot establish current deployed behavior.
