# Mission Framework operational loader — Claude Code

TimeLapse Pro is a Mission Framework reference mission (`github.com/froekjaer/mission-framework`, Apache-2.0). Before substantive work in this repository:

1. Read `Dokumentation/mission-framework/OP-001-Mission-Operational-Preamble.md` in full — a vendored, verbatim copy of the canonical procedure. Apply it: classify the task, verify identifiers, recover existing context, check architectural consistency, search before creating, assess dependencies, execute, then verify the outcome.
2. This repo's authoritative sources — check these before assuming or reconstructing from memory:
   - `Dokumentation/HANDOVER_LOG.md` — session-to-session handover, newest entries at the top of `## Log`.
   - The GRC register (`grc_items` table in production Postgres — `psql "$DATABASE_URL" -c "SELECT external_id, item_type, title, status FROM grc_items WHERE ..."`) — findings, actions, risks, controls with a status field. Check for an existing open item before treating something as new.
   - `Dokumentation/` — topic docs (`SEC-NNN_*.md` security closures, feature docs, risk assessments).
   - `tests/architecture_baseline.json` + `tests/test_architecture_ratchet.py` — a hard, checked-in ratchet on `headend/main.py` size and route count. Never raise the baseline to make a change fit; shrink or extract instead.
   - Open PRs and recent commits (`gh pr list --repo froekjaer/timelapse-pro`, `git log`) — Claude, Codex, ChatGPT, Kimi and Gemini all work on this repo, sometimes concurrently. Do not assume you are the only active session.
3. **Never operate from memory when one of the above is available and unchecked.** This repo has repeatedly rebuilt, half-built, or forgotten the same capability across sessions (see `HANDOVER_LOG.md`, 2026-08-16/17, for concrete, named examples: a security finding closed three separate times without its replacement ever being verified working; a break-glass account built without its key-delivery mechanism; a manifest that silently dropped required files). Search before you build — the thing you're about to create may already exist, half-finished, somewhere in this repo's history or open PRs.
4. After a change: verify the outcome. Read back what you wrote. Run the relevant tests. For anything touching a security or trust boundary, identify what depended on the thing you changed and confirm it still works — not just that your change itself compiles.
5. For substantive work, give a compact preamble status (task classified / sources checked / existing context recovered / dependencies assessed / ready to execute). Skip this for routine conversation that doesn't touch canonical state.

Framework Findings (ambiguity, contradiction, or gap discovered in the framework itself while working here) get recorded and, where material, returned upstream per `docs/FRAMEWORK_FINDINGS.md` in the mission-framework repo.
