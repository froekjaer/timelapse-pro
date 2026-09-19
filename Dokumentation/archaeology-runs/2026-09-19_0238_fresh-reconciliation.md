# Knowledge Archaeology — fresh reconciliation 2026-09-19 02:38 CEST

**Status:** evidence checkpoint; does not declare closure  
**Parent ledger:** `Dokumentation/DOCUMENT_ARCHAEOLOGY_CLOSURE_LEDGER_2026-09-17.md`  
**Detailed v2 reconciliation:** `Dokumentation/DOCUMENT_ARCHAEOLOGY_V2_RECONCILIATION_2026-09-19.md`

## Activity START

Continue branch-aware Knowledge Archaeology against fresh GitHub state. Preserve v2 forensic accounting, do not freeze Golden Capabilities, do not promote archaeology directly into authoritative GRC, and do not merge PR #243.

## Fresh GitHub connector reconciliation

Fresh paginated branch listing was executed through the GitHub connector:

- page 1 = 100 branches;
- page 2 = 39 branches;
- fresh repository branch universe remains **139**;
- `main` remains `928134be847eb96df25455736f6acd766aff84f2` and protected.

Fresh PR #243 metadata:

- state **OPEN**;
- merged **false**;
- mergeable **true**;
- head branch `chatgpt/capability-map-v0-20260916`;
- head before this checkpoint `c4b5c688b582595e0d28eeb604a1584941172e1d`;
- commits **35**;
- changed files **27**;
- additions/deletions **5229 / 0**;
- updated at `2026-09-18T23:11:21Z`.

Fresh compare of current `main` against that head reports **diverged**, archaeology branch **35 ahead / 2 behind**, merge base `8452c5ef264d85823dce149a3bb371142d598569`.

The previous v2 reconciliation recorded PR head `27cc5747...`. Exact compare `27cc5747... → c4b5c688...` is one commit ahead and adds only `Dokumentation/DOCUMENT_ARCHAEOLOGY_V2_RECONCILIATION_2026-09-19.md`. Therefore this head movement does **not** introduce a new product requirement domain; it is archaeology evidence only.

## v2 accounting retained and closure implications

The completed local v2 extraction remains the forensic accounting baseline:

- 20 / 20 configured local roots inspected;
- 139 canonical remote branches represented;
- 177,934 provenance records;
- 20,126 unique raw SHA-256 artifacts;
- 19,976 EXTRACTED;
- 120 SENSITIVE_HOLD;
- 14 UNREADABLE;
- 15 POINTER;
- 1 EMPTY;
- 0 PARTIAL;
- balance 20,126 / 20,126.

Named/path-based universe remains **1,583** unique artifacts, with text recovered for **1,567**. Named residual is **15 POINTER + 1 EMPTY**. All **14 UNREADABLE** artifacts are pathless unreachable candidates rather than named/path-provenanced documents.

This materially changes the old GAP picture: recovered historical DOCX families are no longer merely binary-source-loss candidates because v2 produced local text extractions. However, `extracted` is not automatically equivalent to `strict-read/classified`; each knowledge-bearing version still needs READ/coverage disposition before closure. Sensitive material remains local and must not be published raw.

## GAP reconciliation progress

Current evidence supports the following distinction:

1. **Named residual:** 15 Google pointer sources plus one empty file. These are the only non-text-recovered members of the 1,583 named/path universe. They require equivalence/descendant/source-domain reconciliation, but their existence alone does not prove unique knowledge loss.
2. **Pathless unreadable residual:** 14 unreachable candidates. Because they have no recovered path and no readable text, they remain forensic uncertainty. They are not currently evidenced as `CRITICAL_KNOWLEDGE_GAP`; final novelty/domain assessment is still required.
3. **Historical binary families:** Startkrav, Roadmaps, SABSA Architecture/Risk, Edge Runbooks, RBAC, Security/Compliance and System Inventory have v2 text recovery. Old ledger entries calling them `BINARY_GAP` must therefore be interpreted as historical pre-v2 status pending per-source READ/classification update.
4. **Oversize historical risk source:** connector-size limitation alone is no longer sufficient to call knowledge unavailable when exact-source local extraction exists; equivalence/provenance must be registered before changing `TECHNICAL_GAP` to `COVERED_GAP`.
5. **Critical knowledge:** **0 identified**, but final zero is not yet closure-proven because pointer/pathless novelty reconciliation remains open.

## Requirement/evolution chains retained

No fresh evidence invalidates the established archaeology chains:

- capture autonomy: pre-Git standalone/local-buffer need → SABSA availability attribute → store-and-forward/risk treatment;
- multi-tenancy: pre-Git requirement → roadmap implementation milestone → RBAC/isolation design;
- remote management/update: reverse SSH/direct-Git stages → observed authority/trust/dependency defects → Headend-mediated production direction;
- device identity: bootstrap device/MAC identity → certificate/key-based production trust;
- backup/recovery: backup intent/artifact → RTO/RPO/restore-test requirement; backup existence is not verified recoverability.

Historical completion claims remain evidence claims, not runtime truth. Preserve:

`declared → configured → consumed → executed → runtime reconciled → outcome verified → evidence retained`

and:

`decision/architecture accepted ≠ capability implemented ≠ capability verified`.

## Camera direction

No contrary explicit retirement decision was recovered in this run. Keep current intent:

- Nikon strategic/default for new installations;
- functioning supported legacy Canon retained for migration/backward compatibility;
- defective legacy Edge may be replaced without forcing replacement of a functioning supported camera.

## Remaining closure work

`DATA COLLECTION` remains **OPEN**. Remaining closure gates are:

1. reconcile all 15 named POINTER sources to exact recovered equivalents/descendants or explicit GAP status;
2. novelty/domain-assess the pathless forensic tail, with explicit disposition of 14 UNREADABLE candidates;
3. register exact-source extraction equivalence for old BINARY/oversize GAPs;
4. finish strict READ/classification of knowledge-bearing named versions not already covered;
5. reconcile the malformed-ref history issue in `timelapse-pro-backup` against other object databases/provenance;
6. update the parent closure ledger with v2/final GAP disposition when those gates are satisfied;
7. perform one final fresh branch/main/PR #243 check and state exact final `CRITICAL_KNOWLEDGE_GAP` count.

## Activity RESULT

Actual GitHub connector reconciliation completed. The fresh branch universe remains **139**, current `main` remains `928134be...`, and PR #243 remains open/unmerged. The archaeology head movement since the prior v2 checkpoint was verified as archaeology-documentation-only, not a new product requirement domain. No new `CRITICAL_KNOWLEDGE_GAP` was identified.

**DATA COLLECTION remains OPEN.** Downstream use remains closure ledger → requirement/change/conflict chains → current-intent determination → later authoritative GRC/capability/ADR/usecase/history placement.