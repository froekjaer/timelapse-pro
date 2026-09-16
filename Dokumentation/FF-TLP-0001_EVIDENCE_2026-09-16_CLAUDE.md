# Evidence for FF-TLP-0001 propagation state — TimeLapse Pro Wave 2

**Purpose:** this document is TimeLapse-side evidence intended to later inform an update to Mission Framework's `FF-TLP-0001` (`docs/findings/FF-TLP-0001-cross-repository-governance-propagation.md`, Status: Accepted, Propagation: Open). It is **not** itself an edit to Mission Framework — no file in `froekjaer/mission-framework` is touched by this wave. Mission Framework's own maintainer/decision authority updates that Finding's propagation-target entries when they review this evidence.

**Scope:** TimeLapse Pro Governance Propagation Wave 2, 2026-09-16. Mission Framework Wave 1 reference: PR #13, merge commit `9a1a45435ed0781f987760b00722d4a7700d5052`.

## Propagation target: TimeLapse §16 sub-clause referencing extended Step 7

**Status: addressed.** New `§16.10` added to `Dokumentation/CAPABILITY_REGISTER_FINAL_PROPOSAL_2026-09-13_CLAUDE.md` §3 — a reference to canonical OP-001 Step 7 + Framework Findings, not a restatement of their text. TimeLapse-specific content limited to where completion evidence is recorded locally (`PAKKE_SPOR_REGISTER.md` §14.6 fields, extended this wave; `FF-TLP-0001` for genuinely upstream-relevant lessons).

## Propagation target: TimeLapse OP-001 integration model decision

**Status: closed.** Peter selected architecture **C** (canonical Mission Framework source + controlled local cache/fallback), 2026-09-16. Implemented: `Dokumentation/mission-framework/refresh_op001_cache.py` (check/refresh/bootstrap modes, VERIFIED/STALE/UNKNOWN freshness states, immutable-SHA-pinned fetches, integrity check on fetched content), `Dokumentation/mission-framework/OP-001.provenance.json` (cached revision + freshness metadata), `Dokumentation/mission-framework/README.md` (architecture description). TimeLapse's cached OP-001 copy was migrated from an unmanaged "vendored, verbatim" file to this script-managed cache and re-synced to canonical Wave 1 content (`cached_revision: 9a1a45435ed0781f987760b00722d4a7700d5052`, verified via live check at implementation time).

**Remediated 2026-09-16 (adversarial review, z.ai):** an independent adversarial review reproduced two real implementation defects in the first version of this mechanism: (1) `VERIFIED` could survive local tampering of the cached file, because freshness was checked against canonical but the cached bytes themselves were never verified against anything; (2) the refresh write path could leave a mixed content+provenance pair on a failed write, with no clear error (a raw traceback) and no way to detect or recover from the mismatch. Both were independently reproduced against the reported head before fixing. Fix: added a SHA-256 digest of the cached file's actual bytes to `OP-001.provenance.json`, checked locally (no network needed) before any freshness claim is made; introduced a fourth state, `CORRUPTED`, for a positive digest mismatch; refresh now backs up the current valid pair to `*.prev` before writing, and a subsequent check automatically detects and recovers from an inconsistent active pair rather than ever reporting it as VERIFIED. See `Dokumentation/mission-framework/README.md`'s "Trust model" and "Freshness/integrity states" sections for the corrected, non-overstated semantics (the digest detects local tampering; it does not independently authenticate GitHub).

**Investigation performed before migrating:** confirmed via direct diff that TimeLapse's prior cached body was byte-for-byte identical to the OLD canonical revision (`2db8c2ba1a1f58ce07cdad0e78c35de949b20c09`) it was pinned to — zero TimeLapse-local modifications existed in the body, so no separation/preservation of local changes was needed before re-syncing to the new canonical content.

## Propagation target: mission-framework publication reflects the merged change

**Status: independently verified (from the TimeLapse side, at Wave 1 close-out) — restated here as evidence, not re-verified in this wave.** The Mission Framework close-out already confirmed the live published book (`https://froekjaer.github.io/mission-framework/book/Mission-Framework.md`) contains `FF-TLP-0001`, the "Known findings" index, and the new `Owner` schema field, with `publication-catalog.json`'s `source_commit` matching the merge SHA. Not re-checked in this wave (out of scope — Mission Framework is not modified here).

## New propagation-relevant evidence surfaced this wave

**Governance completion-representation gap, now closed on the TimeLapse side:** prior to this wave, TimeLapse's `PAKKE_SPOR_REGISTER.md` §14.6 fields had no way to represent a cross-repository/publication impact conclusion distinctly from other track fields. This wave added exactly that field (three states: identified+propagated / evidence-backed no-impact / unresolved gap+reference), and a PR-template checkpoint (`W3`, `.github/PULL_REQUEST_TEMPLATE.md`) that prompts for it on every consequential PR going forward. This is TimeLapse's concrete downstream implementation of the obligation OP-001 Step 7 states generically — offered here as evidence that the upstream rule is actually being operationalized by at least one downstream consumer, not remaining paper-only.

## Still-open downstream propagation gaps (not addressed by TimeLapse; not this repository's to fix)

- Collaborative Intelligence: published `index.html` vs README/AI_CONTEXT.md divergence.
- Mission Platform: published site presents ADR content matching no real ADR file; ADR index omits `ADR-0002`.
- No TimeLapse action was taken on either — both remain the respective repository owners' decisions, per Peter's explicit instruction not to modify those repositories in this wave.

## Verification and hardening lineage (updated 2026-09-16, ChatGPT-directed review)

Beyond the initial implementation, this mechanism went through two further rounds of adversarial verification before being considered ready for merge review, all on TimeLapse PR #241 (stacked on #240):

1. **z.ai adversarial review** reproduced two real defects (VERIFIED surviving local tampering; a non-transactional refresh write path that could leave a mixed content+provenance pair with an uncaught traceback on failure). Both independently reproduced, then fixed: a content digest now binds local bytes to recorded provenance (checked before any freshness claim, no network required), a new `CORRUPTED` state for a positive mismatch, and a backup-then-atomic-replace refresh transaction with automatic detect-and-recover via `*.prev`.
2. **ChatGPT-directed review** found a further, real semantic gap: the mandatory loader instruction told an agent to run the integrity check but never gated consequential work on what it reported — a compliant-but-hostile reading could run the script, ignore its output, and proceed anyway. Fixed: all four loader files now map each of VERIFIED/STALE/UNKNOWN/CORRUPTED to a required action, verified for semantic parity across all four by an automated test (`tests/test_op001_loader_instructions.py`). Also fixed: canonical authority was not explicitly named in CLI output; the `.prev` recovery mechanism was adversarially re-tested (active+backup both corrupted; two consecutive interrupted refreshes) with no further defect found.

31+ automated tests now cover this mechanism (`tests/test_op001_cache.py`, `tests/test_op001_loader_instructions.py`), plus repeated manual failure-mode verification with actual byte/metadata inspection (not exit-code inference alone).

## Recommendation for the Finding's propagation-target entries

Based on the above, Mission Framework's maintainer may wish to update `FF-TLP-0001`'s "Propagation targets (not yet closed)" list to move the "TimeLapse §16 sub-clause" and "TimeLapse OP-001 integration decision" entries to closed/addressed, with a reference to this document and to TimeLapse PR(s) implementing Wave 2 (see HANDOVER_LOG.md, 2026-09-16 entry, for exact PR reference once opened). This document does not itself make that edit — it is evidence for whoever holds that decision.

**Evidence reference to send upstream after merge:** once TimeLapse PR #240 and #241 are merged, the reference to send to Mission Framework's maintainer is the final post-merge commit SHA on TimeLapse `main` (not a pre-merge branch SHA, which will no longer resolve the same way) plus this document's path (`Dokumentation/FF-TLP-0001_EVIDENCE_2026-09-16_CLAUDE.md`). This has **not** been sent upstream yet, and `FF-TLP-0001` itself has **not** been marked closed — both remain explicitly open, pending Peter's merge authorization and Mission Framework's own review of this evidence.
