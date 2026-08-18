# Mission Framework operational loader — Gemini CLI

TimeLapse Pro is a Mission Framework reference mission (`github.com/froekjaer/mission-framework`, Apache-2.0). Before substantive work in this repository:

1. Read `Dokumentation/mission-framework/OP-001-Mission-Operational-Preamble.md` — a vendored, verbatim copy of the canonical procedure — and apply it: classify the task, verify identifiers, recover existing context, check architectural consistency, search before creating, assess dependencies, execute, then verify the outcome.
2. This repo's authoritative sources — check these before assuming or reconstructing from memory:
   - `Dokumentation/HANDOVER_LOG.md` — session-to-session handover, newest entries at the top of `## Log`.
   - The GRC register (`grc_items` table in production Postgres, queryable via `psql`) — findings, actions, risks, controls with a status field.
   - `Dokumentation/` topic docs (`SEC-NNN_*.md` security closures, feature docs, risk assessments).
   - `tests/architecture_baseline.json` + `tests/test_architecture_ratchet.py` — a hard ratchet on `headend/main.py` size; never raise the baseline to make a change fit.
   - `gh pr list --repo froekjaer/timelapse-pro` and `git log` — Claude, Codex, ChatGPT, Kimi and Gemini all work on this repo, sometimes concurrently.
3. Never operate from memory when one of the above is available and unchecked. This repo has repeatedly rebuilt, half-built, or forgotten the same capability across sessions — see `HANDOVER_LOG.md` 2026-08-16/17 for named examples. Search before you build.
4. After a change: verify the outcome by reading back what you wrote and running the relevant tests. For anything touching a security or trust boundary, confirm what depended on the changed thing still works.
5. For substantive work, give a compact preamble status; skip it for routine conversation that doesn't touch canonical state.
