# Mission Framework OP-001 — canonical source with controlled local cache

TimeLapse Pro is a named reference mission in [`froekjaer/mission-framework`](https://github.com/froekjaer/mission-framework) (Apache-2.0) — see that repo's `README.md` and `MISSION.md` for the framework's continuity and independent-verification proposition, which this project is expected to test in practice.

## Architecture: C — canonical source + controlled local cache/fallback

Decided by Peter, 2026-09-16, as part of the approved Cross-Repository Governance Propagation architecture (see `FF-TLP-0001` in mission-framework and `Dokumentation/CROSS_REPOSITORY_GOVERNANCE_PROPAGATION_ANALYSIS_2026-09-14_CLAUDE.md` §16 item 9).

- **Canonical authority:** `froekjaer/mission-framework`, path `docs/operational/OP-001-Mission-Operational-Preamble.md`. TimeLapse does not maintain an independently authoritative fork of OP-001.
- **`OP-001-Mission-Operational-Preamble.md`** in this folder is a **cached, script-managed, byte-for-byte mirror** of that canonical file. It is written **only** by `refresh_op001_cache.py` — never hand-edited. This keeps operational governance usable when GitHub or network access is unavailable, per the framework's own continuity principle ("no single external source shall be the sole carrier of mission-critical knowledge").
- **`OP-001.provenance.json`** in this folder records the exact cached source commit, when it was last checked against canonical, and the current freshness state:
  - `VERIFIED` — canonical was reachable and its HEAD SHA was compared directly to the cached revision (and matched, or the cache was just refreshed to it).
  - `STALE` — canonical was reachable and its HEAD SHA differs from the cached revision. Evidence-based, never guessed.
  - `UNKNOWN` — canonical could not be reached this check. The cache remains usable at its last known state; freshness for *this* session is simply not established, and must not be reported as VERIFIED or STALE without evidence.
- **`refresh_op001_cache.py`** is the explicit refresh mechanism:
  - `python3 refresh_op001_cache.py` — check freshness only, does not modify the cache.
  - `python3 refresh_op001_cache.py --refresh` — if STALE, fetch and apply the new canonical content (review and commit the result yourself; never applied silently).
  - `python3 refresh_op001_cache.py --bootstrap` — (re)create the cache and provenance file from scratch, for first-time setup or recovery.
  - Fetches over HTTPS from `api.github.com`/`raw.githubusercontent.com` only; pins content fetches to an immutable commit SHA obtained in the same run (never a mutable branch reference); runs a basic integrity check on fetched content before applying it; never invokes a shell, so there is no injection surface from this mechanism.

## Auditability

Which OP-001 revision governed a piece of consequential work is recoverable from `OP-001.provenance.json`'s `cached_revision` at the time, combined with the work's own Visible Preamble Record entry (reused from OP-001 §8 — no second audit system is introduced here).

## Offline / degraded-connectivity operation

If canonical cannot be reached, an agent should still be able to start and continue consequential work using the cached copy, with the freshness state visible as `UNKNOWN` rather than silently or falsely reported as current. Whether stale/unknown governance state requires a warning, a recovery attempt, a registered gap, or a stop, is a materiality judgement — not an unconditional block — per the same risk/evidence principles already governing the rest of this project's operational discipline (`SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` §16).

## Collaborator loaders

The five AI collaborators active on this repo (Claude, Codex CLI, ChatGPT, Kimi Code, Gemini) are covered by four loader surfaces, since Codex CLI and Kimi Code both read the same file:

- `CLAUDE.md` (repo root) — Claude
- `AGENTS.md` (repo root) — Codex CLI and Kimi Code
- `GEMINI.md` (repo root) — Gemini
- `Dokumentation/CHATGPT-PROJECT-INSTRUCTIONS.md` — ChatGPT (the chat product has no repo-file auto-load convention; this file is for manual insertion into its project instructions)

Each loader points back to this folder's cached OP-001 plus this repo's own authoritative sources (`HANDOVER_LOG.md`, the GRC register, `PAKKE_SPOR_REGISTER.md`, `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md`) rather than restating canonical text.

## Divergence and disagreement

If a TimeLapse-local need appears to require a different rule than canonical OP-001 states, or if this cache and canonical upstream disagree in a way `--refresh` doesn't resolve, treat that as a candidate Framework Finding (`docs/FRAMEWORK_FINDINGS.md` upstream, see `FF-TLP-0001`) — never as license to hand-edit this cache.
