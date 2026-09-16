# ChatGPT project instructions — TimeLapse Pro

**This file is not auto-loaded.** Unlike Claude Code (`CLAUDE.md`), Codex/Kimi Code (`AGENTS.md`), and Gemini CLI (`GEMINI.md`), the ChatGPT chat product has no convention for automatically reading a file from a repository. Paste the block below into ChatGPT's Project custom instructions (or the system/developer prompt) when starting a ChatGPT session that will work on TimeLapse Pro.

If the session is actually using OpenAI's Codex agent rather than chat-based ChatGPT, use `AGENTS.md` at the repo root instead — Codex reads that automatically and this file is unnecessary.

---

TimeLapse Pro is a Mission Framework reference mission (`github.com/froekjaer/mission-framework`, Apache-2.0). Before substantive work in this repository, read and follow `Dokumentation/mission-framework/OP-001-Mission-Operational-Preamble.md` — a vendored, verbatim copy of the canonical operational procedure.

Before acting, check this repo's authoritative sources rather than relying on memory or assumption:
- `Dokumentation/HANDOVER_LOG.md` — session-to-session handover, newest entries at the top of `## Log`.
- The GRC register (`grc_items` table in production Postgres, queryable via `psql`) — findings, actions, risks, controls with a status field. Check for an existing open item before treating something as new.
- `Dokumentation/` topic docs (`SEC-NNN_*.md` security closures, feature docs, risk assessments).
- `tests/architecture_baseline.json` + `tests/test_architecture_ratchet.py` — a hard ratchet on `headend/main.py` size and route count. Never raise the baseline to make a change fit.
- `gh pr list --repo froekjaer/timelapse-pro` and `git log` — Claude, Codex, ChatGPT, Kimi and Gemini all work on this repo, sometimes concurrently. Do not assume you are the only active session.

This repo has repeatedly rebuilt, half-built, or forgotten the same capability across sessions — see `HANDOVER_LOG.md` 2026-08-16/17 for concrete, named examples (a security finding closed three separate times without its replacement ever being verified working; a break-glass account built without its key-delivery mechanism; a release manifest that silently dropped required files). Search before you build. After a change, verify the outcome — read back what you wrote, run the relevant tests, and for anything touching a security or trust boundary, confirm what depended on the changed thing still works. Consequential capability changes (new implementation, or a deployment/update/dependency rollout) additionally have an architecture-approved-but-not-yet-formally-accepted governance discipline (Peter, 2026-09-14): identify capability intent/invariants, relevant usecases, authoritative and historical implementation (an explicit `git log --all` search, not just current main), and verification; the change is not complete until its runtime health is observed afterward, not merely deployed. Prefer reuse over extension over new construction; place generic cross-project functionality upstream rather than building a TimeLapse-local parallel, unless a thin, non-competing, non-locking local prototype is explicitly justified. See `Dokumentation/CAPABILITY_REGISTER_FINAL_PROPOSAL_2026-09-13_CLAUDE.md` (section 16) for the full text and open decisions.
