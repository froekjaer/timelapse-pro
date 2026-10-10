# Knowledge Archaeology — v2 accounting + fresh reconciliation

**Timestamp:** 2026-09-18 15:15 CEST  
**Status:** evidence checkpoint; does not declare closure  
**Parent ledger:** `Dokumentation/DOCUMENT_ARCHAEOLOGY_CLOSURE_LEDGER_2026-09-17.md`  
**Detailed reconciliation:** `Dokumentation/DOCUMENT_ARCHAEOLOGY_V2_RECONCILIATION_2026-09-18.md`

## Activity START

Continue Knowledge Archaeology with the completed local v2 forensic extraction as a discovery/evidence layer, then reconcile it against fresh GitHub state. No Golden Capability freeze, no direct promotion into authoritative GRC, and no merge of PR #243.

## Fresh GitHub state

A fresh paginated GitHub branch query at this checkpoint returns exactly **139 repository branches**: 100 + 39 + 0 after cursor 139. No branch-count drift is observed.

Fresh `main` remains `928134be847eb96df25455736f6acd766aff84f2` (Wave 2 governance merge #241).

Fresh PR #243 metadata: **OPEN / UNMERGED**, base `main`, recorded base SHA `8452c5ef264d85823dce149a3bb371142d598569`, head `chatgpt/capability-map-v0-20260916` at `c22f0a14fb4c8d601fad985977cbd1e00ba65f91`, 27 commits / 21 changed files at this checkpoint. Fresh compare against current main reports `diverged`, archaeology head **27 ahead / 2 behind**, merge base `8452c5ef264d85823dce149a3bb371142d598569`.

The 21 changed files are archaeology/capability evidence documents only. This remains a working evidence branch, not merged/current product authority.

## Local forensic v2 accounting carried into closure work

Completed v2 extraction supplied to the archaeology work reports:

- configured/existing local roots inspected: **20**;
- canonical origin remote-tracking branches observed by the local scanner: **139**;
- provenance records: **177,934**;
- unique raw SHA-256 artifacts: **20,126**;
- `EXTRACTED`: **19,976**;
- `SENSITIVE_HOLD`: **120**;
- `UNREADABLE`: **14**;
- `POINTER`: **15**;
- `EMPTY`: **1**;
- `PARTIAL`: **0**;
- accounting balance: **20,126 / 20,126**.

This balance proves disposition only for artifacts discovered by v2. It is not sufficient to declare Knowledge Archaeology closed.

The local reconciliation further separates the evidence populations: **1,583 unique artifacts have named/path-based provenance**. Text is recoverable for **1,567** of those; the residual named set is **15 Google pointer artifacts + 1 empty artifact**. The 14 `UNREADABLE` candidates are pathless unreachable blobs, not members of the named/path-provenanced set. The much larger pathless/unreachable population remains a separate forensic reconciliation tail and must not be represented as an equivalent set of human-authored documents.

## GAP reconciliation delta

Earlier blanket `BINARY_GAP` treatment for recovered historical DOCX families is stale after v2 extraction. Recovered binaries with local text extraction must be reconciled per unique content/provenance as `READ` after full content review, or retain an explicit residual GAP. `SENSITIVE_HOLD` is recoverable local evidence, not source loss; derived requirement/decision findings may be recorded without publishing credential-like raw text.

Current residual classes requiring closure disposition:

- **15 POINTER** named artifacts: source/reference resolution or `COVERED_GAP` assessment required.
- **1 EMPTY** named artifact: assess whether knowledge-bearing; current evidence indicates no unique requirement domain, but final disposition remains part of closure accounting.
- **14 UNREADABLE** pathless unreachable blobs: forensic `TECHNICAL_GAP`/`BINARY_GAP` candidates until novelty/knowledge-domain risk is assessed.
- local `timelapse-pro-backup` malformed-ref history enumeration remains a `TECHNICAL_GAP`; filesystem evidence was recovered, but object-database/history completeness must be reconciled against other roots before closure.
- pathless/unreachable candidates require novelty reduction against named content/provenance before `CRITICAL_KNOWLEDGE_GAP` can be set to an exact final count.

No new `CRITICAL_KNOWLEDGE_GAP` is identified by this checkpoint. This is deliberately **not** the same as proving the final count is zero.

## Requirement-history findings preserved

The extracted historical material supports preserving these evolution chains for later synthesis rather than treating older implementation choices as deleted requirements:

- capture autonomy/store-and-forward: pre-Git need → formal availability attribute → later runtime/implementation evidence;
- multi-tenancy: pre-Git requirement → roadmap implementation milestone → RBAC/isolation design/evolution;
- remote management/update: reverse-SSH/direct-Git historical solutions → identified production conflict → Headend-mediated controlled update direction;
- device identity: MAC/bootstrap convenience → certificate/key-based production trust direction;
- backup/recovery: backup existence/configuration must remain distinct from restore/RTO/RPO verification;
- camera platform: Nikon remains strategic/default for new installations while supported functioning legacy Canon remains current migration/backward-compatibility intent.

Historical claims such as `LØST`, `production ready`, or `implemented` remain historical claims unless separately supported by implementation/runtime/evidence maturity. Disappearance from later documents is not supersession.

## Activity PROGRESS / RESULT

This checkpoint closes the fresh-state recheck for this run: branch universe remains 139, current main is unchanged, PR #243 remains open/unmerged and has advanced through archaeology-only evidence commits. The v2 extraction materially reduces the old binary/source-loss uncertainty, but data collection is **not closed** because pointer disposition, pathless/unreadable novelty assessment, malformed-ref object-history reconciliation, exact all-branch path/blob accounting, and final `CRITICAL_KNOWLEDGE_GAP` count remain unresolved.

Downstream use: this checkpoint feeds the closure ledger and later requirement/change/conflict chains. It is not an authoritative GRC source and must not itself freeze Golden Capabilities.
