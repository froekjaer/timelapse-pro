# Knowledge Archaeology — fresh reconciliation 2026-09-18 23:44 CEST

**Status:** evidence checkpoint; does not declare closure  
**Parent ledger:** `Dokumentation/DOCUMENT_ARCHAEOLOGY_CLOSURE_LEDGER_2026-09-17.md`  
**Detailed v2 reconciliation:** `Dokumentation/DOCUMENT_ARCHAEOLOGY_V2_RECONCILIATION_2026-09-18.md`

## Activity START

Continue branch-aware Knowledge Archaeology against fresh GitHub state. Preserve the completed local v2 forensic accounting, do not freeze Golden Capabilities, do not promote archaeology directly into authoritative GRC, and do not merge PR #243.

## Fresh GitHub connector reconciliation

Fresh repository branch inventory was executed again through the GitHub connector:

- page 1: 100 branches;
- page 2: 39 branches;
- exact repository branch universe remains **139**;
- `main` remains `928134be847eb96df25455736f6acd766aff84f2`.

Fresh PR #243 metadata:

- state: **OPEN**;
- merged: **false**;
- head branch: `chatgpt/capability-map-v0-20260916`;
- head SHA before this checkpoint: `8870976132f3eb6d6bca6ed49c1ad50e486f9772`;
- commits: **33**;
- changed files: **25**;
- updated at: `2026-09-18T20:11:44Z`.

Fresh compare of current `main` against that head reports **diverged**, archaeology branch **33 ahead / 2 behind**, merge base `8452c5ef264d85823dce149a3bb371142d598569`.

The compare shows the archaeology branch now includes the v2 reconciliation and multiple dated run checkpoints in addition to the working index/register/ledger. These remain unmerged working evidence, not current product authority.

## Strict-read evidence delta — historical System Health Register

The historical `Dokumentation/SYSTEM_HEALTH_REGISTER.md` at commit `443c5e0bd9f926f8838143d9fc51f7283fa9072c`, blob `58bf9b155dd40e8aae67e470558b98e4da058f38`, was connector-read again in three non-overlapping ranges covering the complete source (1–120, 121–240, 241–end).

Direct source evidence confirms all **HLTH-001..HLTH-015** and the final remediation/open-decision section. Archaeology-relevant conclusions are:

1. `HLTH-003` explicitly records direct Edge GitHub/origin update as conflicting with the requirement that production Edge may lack Internet and should update through Headend. The proposed remediation is Headend-mediated signed release artifacts with per-target reporting.
2. `HLTH-004` records the integrity defect where a signed tag was verified but `origin/main` was installed; therefore signature evidence was not bound to the executed object.
3. `HLTH-005` records visible approval choices that were not sent in the API action; therefore operator-visible approval did not bind actual environment/scope/targets.
4. `HLTH-007` records the required scope as `global|customer|site|camera|device` and proposes binding camera scope to `DeviceAssignment`, preserving policy history across physical device replacement.
5. `HLTH-008` records that aggregate `PendingUpdate.status` cannot represent per-target truth for multi-target rollout/rollback.
6. `HLTH-009` records that maintenance/reboot policy could be returned without being consumed/enforced by Edge.
7. `HLTH-010` records production JWT configuration needing fail-closed startup rather than silent random-secret fallback.
8. `HLTH-012..014` distinguish build/lint/test presence from meaningful integration/runtime evidence.
9. The final remediation section explicitly proposes documenting `edge_update.sh` as **legacy/LAB-only** until Headend artifact update exists. This is direct supersession rationale rather than disappearance-based inference.

Status remains **READ / EXTRACTED / HISTORICAL ASSESSMENT**. No unique previously unknown requirement domain and no evidence of a `CRITICAL_KNOWLEDGE_GAP` was exposed by this repeat strict-read.

## v2 accounting retained

Completed local v2 forensic accounting remains the current extraction baseline:

- 20 local roots inspected;
- 139 canonical origin remote-tracking branches observed;
- 177,934 provenance records;
- 20,126 unique raw SHA-256 artifacts;
- 19,976 EXTRACTED;
- 120 SENSITIVE_HOLD;
- 14 UNREADABLE;
- 15 POINTER;
- 1 EMPTY;
- 0 PARTIAL;
- balance 20,126 / 20,126.

Named/path-provenanced evidence remains separated from pathless forensic candidates: **1,583** unique named/path artifacts, text recoverable for **1,567**, with named residual **15 POINTER + 1 EMPTY**. The **14 UNREADABLE** candidates are pathless unreachable blobs.

## GAP position

No evidence recovered in this run establishes a `CRITICAL_KNOWLEDGE_GAP`. Exact final count is still **not proven zero**.

Residual closure work remains:

1. exact final branch → document path → unique blob SHA reconciliation against the fresh 139-branch universe;
2. novelty/domain reduction of pathless/unreachable forensic candidates;
3. final disposition of 15 named POINTER, 1 named EMPTY, 14 pathless UNREADABLE, and relevant SENSITIVE_HOLD evidence;
4. reconciliation of the `timelapse-pro-backup` malformed-ref Git-history `TECHNICAL_GAP` against other recovered object databases/provenance;
5. strict-complete review/classification of remaining knowledge-bearing named versions where not already covered;
6. exact `CRITICAL_KNOWLEDGE_GAP` count;
7. final fresh main/branch/PR reconciliation at closure time.

Historical/current camera intent remains unchanged: Nikon strategic/default for new installations; supported functioning legacy Canon remains current migration/backward-compatibility intent unless an explicit retirement decision with rationale is recovered.

## Activity RESULT

Fresh GitHub state has been actively reconciled. Repository branch count remains **139**, `main` remains `928134be...`, and PR #243 remains open/unmerged while its working archaeology head reached `8870976...` before this checkpoint. Historical System Health Register has been strict-read again from primary source and its supersession rationale/evidence boundaries remain confirmed.

**DATA COLLECTION remains OPEN.** Downstream use remains: closure ledger → requirement/change/conflict chains → current-intent determination → later authoritative GRC/capability/ADR/usecase/history placement.