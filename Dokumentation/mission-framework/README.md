# Mission Framework OP-001 — canonical source with controlled local cache

TimeLapse Pro is a named reference mission in [`froekjaer/mission-framework`](https://github.com/froekjaer/mission-framework) (Apache-2.0) — see that repo's `README.md` and `MISSION.md` for the framework's continuity and independent-verification proposition, which this project is expected to test in practice.

## Architecture: C — canonical source + controlled local cache/fallback

Decided by Peter, 2026-09-16, as part of the approved Cross-Repository Governance Propagation architecture (see `FF-TLP-0001` in mission-framework and `Dokumentation/CROSS_REPOSITORY_GOVERNANCE_PROPAGATION_ANALYSIS_2026-09-14_CLAUDE.md` §16 item 9).

- **Canonical authority:** `froekjaer/mission-framework`, path `docs/operational/OP-001-Mission-Operational-Preamble.md`. TimeLapse does not maintain an independently authoritative fork of OP-001.
- **`OP-001-Mission-Operational-Preamble.md`** in this folder is a **cached, script-managed, byte-for-byte mirror** of that canonical file. It is written **only** by `refresh_op001_cache.py` — never hand-edited.
- **`OP-001.provenance.json`** records the cached source commit, a SHA-256 digest of the cached file's actual bytes, and the current freshness/integrity state.
- **`refresh_op001_cache.py`** is the explicit check/refresh/bootstrap mechanism (see below).

## Freshness/integrity states

Two independent questions, checked separately every time:

- **Local integrity** — do the cached file's actual bytes match the digest `OP-001.provenance.json` recorded for them? Purely local, needs no network, checked first, always.
- **Remote freshness** — does canonical's current HEAD match the cached revision? Needs network.

| State | Meaning |
|---|---|
| `VERIFIED` | Local integrity confirmed, **and** canonical was reachable and its HEAD matched the cached revision (or the cache was just refreshed to it) — or canonical was unreachable but the cache was already VERIFIED at its last real check. |
| `STALE` | Local integrity confirmed; canonical was reachable and its HEAD differs from the cached revision. Evidence-based, never a guess. |
| `UNKNOWN` | Freshness/integrity cannot currently be established — canonical unreachable, or the provenance record has no digest to check against (e.g. an old-format file). The cache remains usable at its last known state; this is not itself an error, and is never silently upgraded to VERIFIED. |
| `CORRUPTED` | The cached file's actual bytes do **not** match the digest recorded for them. Never silently rewritten. If a `*.prev` backup exists and is itself internally consistent, it is restored automatically; otherwise the cache is not usable with confidence and `--bootstrap` is required. |

**A `*.prev` backup pair** (`OP-001-Mission-Operational-Preamble.md.prev` + `OP-001.provenance.json.prev`) is kept alongside the active pair — the last known-good state before the most recent refresh. `--refresh` writes the new content and provenance to temporary files in the same directory, fsyncs them, then applies them via two `os.replace()` calls. Those two calls are not atomic as a pair: if a failure happens between them, the active pair can end up mismatched (new content, old provenance, or vice versa). This is not silently trusted — the local-integrity check above catches exactly that mismatch on the next run and automatically recovers from the `*.prev` backup, reporting `VERIFIED (recovered)` with the reason. The refresh mechanism guarantees *detect-and-recover*, not full two-file OS-level atomicity; that distinction is deliberate, not an oversight.

## Trust model — read this before assuming more than it provides

The content digest binds the cached bytes to the provenance record this script itself wrote after a previous successful fetch from canonical. It proves *"these bytes are the ones this repository previously fetched and recorded"* — i.e. it detects **local** tampering or corruption after the fact. It does **not** independently authenticate GitHub and does **not** create a cryptographic trust anchor beyond ordinary HTTPS: the digest and the content it describes both originate from the same remote trust domain at fetch time. A compromise of that domain at the moment of fetch is not detected by this mechanism. Four distinct things, kept separate:

- **Canonical revision discovery** — yes, via the GitHub API over HTTPS.
- **Remote content consistency** — yes, between the SHA check and the content fetch within the same run (immutable-SHA-pinned, no mutable-ref window).
- **Local content integrity** — yes, after the fact, against this script's own previously recorded digest.
- **Source authenticity** — **not** independently established. This script trusts GitHub's TLS certificate and API response at fetch time, the same as any HTTPS client. It adds no signature or separate trust anchor.

## What actually reads OP-001, and what "VERIFIED" covers

Loaders (`CLAUDE.md`/`AGENTS.md`/`GEMINI.md`/`Dokumentation/CHATGPT-PROJECT-INSTRUCTIONS.md`) instruct an agent to read `OP-001-Mission-Operational-Preamble.md` directly, as plain Markdown — that read does **not** itself invoke `refresh_op001_cache.py` or check the content digest. "VERIFIED" describes the state `refresh_op001_cache.py` last established, not a guarantee that automatically re-applies to every subsequent plain file read. For consequential work (per `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` §16.1), run `python3 Dokumentation/mission-framework/refresh_op001_cache.py` before relying on this file — the local-integrity half of that check needs no network and is fast, so it does not make offline startup fragile; it only tells you, honestly, whether what you are about to read is the state this mechanism last vouched for.

## Auditability

Which OP-001 revision governed a piece of consequential work is recoverable from `OP-001.provenance.json`'s `cached_revision` at the time, combined with the work's own Visible Preamble Record entry (reused from OP-001 §8 — no second audit system is introduced here).

## Offline / degraded-connectivity operation

If canonical cannot be reached, an agent should still be able to start and continue consequential work using the cached copy, with the freshness state visible as `UNKNOWN` rather than silently or falsely reported as current. Tampered/inconsistent local state and unavailable upstream are different conditions and are reported differently (`CORRUPTED` vs `UNKNOWN`) — network failure alone is never reported as evidence of tampering, and local tampering is detected the same way whether or not canonical happens to be reachable. Whether stale/unknown/corrupted governance state requires a warning, a recovery attempt, a registered gap, or a stop is a materiality judgement — not an unconditional block — per the same risk/evidence principles already governing this project's operational discipline (`SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md` §16).

## Collaborator loaders

The five AI collaborators active on this repo (Claude, Codex CLI, ChatGPT, Kimi Code, Gemini) are covered by four loader surfaces, since Codex CLI and Kimi Code both read the same file:

- `CLAUDE.md` (repo root) — Claude
- `AGENTS.md` (repo root) — Codex CLI and Kimi Code
- `GEMINI.md` (repo root) — Gemini
- `Dokumentation/CHATGPT-PROJECT-INSTRUCTIONS.md` — ChatGPT (the chat product has no repo-file auto-load convention; this file is for manual insertion into its project instructions)

Each loader points back to this folder's cached OP-001 plus this repo's own authoritative sources (`HANDOVER_LOG.md`, the GRC register, `PAKKE_SPOR_REGISTER.md`, `SAMARBEJDSMODEL_PETER_CLAUDE_CODEX_v1.md`) rather than restating canonical text.

## Divergence and disagreement

If a TimeLapse-local need appears to require a different rule than canonical OP-001 states, or if this cache and canonical upstream disagree in a way `--refresh` doesn't resolve, treat that as a candidate Framework Finding (`docs/FRAMEWORK_FINDINGS.md` upstream, see `FF-TLP-0001`) — never as license to hand-edit this cache.
