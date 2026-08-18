# Mission Framework operational loader — Codex / Kimi Code

This file is read by both OpenAI Codex CLI and Moonshot Kimi Code (both follow the `AGENTS.md` convention). If you are a different agent that also reads `AGENTS.md`, the same instructions apply to you.

TimeLapse Pro is a Mission Framework reference mission (`github.com/froekjaer/mission-framework`, Apache-2.0). For substantive work in this repository:

1. Read and follow `Dokumentation/mission-framework/OP-001-Mission-Operational-Preamble.md` — a vendored, verbatim copy of the canonical procedure — before making changes.
2. Inspect existing files, Git state, and identifiers before creating or modifying anything. Treat remembered or inferred operational facts as unverified until confirmed against:
   - `Dokumentation/HANDOVER_LOG.md` — newest entries at the top of `## Log`.
   - The GRC register (`grc_items` table in production Postgres, queryable via `psql`) — findings/actions/risks with status; check for an existing open item before assuming something is new.
   - `Dokumentation/` topic docs (`SEC-NNN_*.md` and others).
   - `tests/architecture_baseline.json` / `tests/test_architecture_ratchet.py` — a hard ratchet on `headend/main.py`; never raise the baseline to fit a change.
   - `gh pr list --repo froekjaer/timelapse-pro` and `git log` — other AI sessions (Claude, Codex, ChatGPT, Kimi, Gemini) work on this repo, sometimes concurrently.
3. Search before create; stop when required authoritative state is missing or conflicting rather than inventing it. This repo has repeatedly rebuilt or forgotten the same capability across sessions — see `HANDOVER_LOG.md` 2026-08-16/17 for named examples.
4. After changes: inspect the diff, read back affected files, and run the relevant tests. For anything touching a security or trust boundary, confirm what depended on the changed thing still works.
5. Show only a compact preamble status unless full detail is requested.

Do not activate this procedure for routine conversation or explanation that cannot alter operational or canonical state.
