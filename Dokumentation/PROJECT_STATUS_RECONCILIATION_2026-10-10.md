# TimeLapse Pro — Consolidated Project Status Review

**Date:** 2026-10-10  
**Status:** WORKING REVIEW — pre-GRC reconciliation  
**Branch:** `chatgpt/consolidated-project-catalog-20261010`

## 1. Objective

Create one human-reviewable reconciliation of TimeLapse Pro history before GRC is updated. This document is intentionally a temporary review surface, not a competing source of truth.

## 2. Confirmed governance facts

1. The project explicitly designated PostgreSQL `grc_items`, `grc_links`, `grc_test_runs`, and `grc_evidence` as authoritative GRC status from 2026-07-16.
2. Historical documents continued to evolve after that migration and therefore contain findings/decisions that may not be represented accurately in GRC.
3. `MASTER_REVIEW_CLOSURE_2026-08-15.md` says broad review was complete for its baseline and requires objective evidence before CLOSED.
4. Later September/October work and open PRs materially post-date that closure baseline.
5. Therefore neither old documents, current GRC, nor open PR count alone can represent current project completion.

## 3. Provisional workstream reconciliation

| Workstream | Historical state | Current reconciliation need | Provisional state |
|---|---|---|---|
| Security/RBAC/secrets | Many review findings closed; later mTLS/security work continues | Map C-series, findings, later mTLS PRs and current main to GRC | PARTIAL / mixed |
| Edge API mTLS / PKI | Earlier go-live gap; WP-4 changed architecture | Reconcile PR #246 + stacked #259, deployed evidence, revocation/lifecycle | OPEN / IMPLEMENTED-UNVERIFIED mix |
| Update flow | Major signing/deploy controls closed in Aug; reliability items remained | Re-evaluate U-01..U-15 against current main and newer PRs | PARTIAL |
| Edge provisioning / Golden Edge | WP-4 target established; reproducibility gaps later found | Reconcile #257, #256, builder and physical Edge state | PARTIAL |
| Remote/technician/SSH | Browser terminal and grants evolved repeatedly | Reconcile #274 against Oct tunnel/wake changes (#290/#291 merged) | SUPERSESSION REVIEW REQUIRED |
| AI / image intelligence | Existing AI functions plus newer provider architecture | Reconcile #258 with current Apple/Ollama/Gemini paths and GRC AI inventory | PARTIAL / DESIGN |
| Backup/restore | Repeatedly a go-live evidence gap | Verify whether a current real restore rehearsal now exists | IMPLEMENTED-UNVERIFIED until evidence |
| Compliance/GDPR/CRA/NIS2/ISO | Documentation substantially expanded | Distinguish technical controls from legal/customer acceptance evidence | PARTIAL |
| UI/UX | July registers are stale; many later changes | New current-UI reconciliation rather than reuse old percentages | UNKNOWN pending current check |
| Observability/operations | Earlier partial state, later health/alert changes | Map live evidence and current system health | PARTIAL |
| Architecture/technical debt | main.py monolith governed by ratchet | Check current debt against later extractions and current tests | MITIGATING |
| Physical RC / deployed Edges | Cannot close from source review | Require current physical/operational evidence | OPEN unless newer evidence found |

## 4. Known historical quantitative snapshot — NOT current

An older requirement register reported 82 items: 42 implemented, 29 partial, 11 missing (51% / 35% / 13%). The document itself records that not all rows were subsequently cross-checked. These figures are retained only as historical evidence and MUST NOT be presented as current project completion.

## 5. GRC reconciliation rule

For each candidate item, record:
- canonical ID / proposed canonical ID;
- source document(s);
- earliest date;
- latest relevant evidence;
- GRC record/link if present;
- code/PR/commit evidence;
- physical/operational evidence where required;
- implementation state;
- verification state;
- supersession relationship;
- proposed GRC action: NONE / UPDATE / LINK EVIDENCE / CREATE / SUPERSEDE / CLOSE;
- Peter decision required: yes/no.

No GRC mutation should be performed from this working review until the candidate has been reconciled and reviewed.

## 6. Immediate priority queue

### P0 — reconstruct authoritative state
- Extract GRC identities/links represented in repository artifacts.
- Deduplicate Master Review C/U-series, Codex-Audit findings, 3P findings, requirement IDs and package tracks.
- Reconcile all 17 open PRs against current main and the candidate list.

### P1 — verify release-critical evidence
- mTLS/PKI live assurance.
- backup/restore rehearsal.
- signed offline OS update and rollback evidence.
- deployed Edge convergence/commissioning.
- production exposure/network acceptance.
- GDPR/customer legal acceptance where applicable.

### P2 — completion and debt
- AI provider architecture.
- UI/current use-case coverage.
- observability/background-job health.
- monolith/settings/config hygiene.
- stale branches/docs and superseded PR closure.

## 7. Review output expected before GRC update

The next revision should contain a deduplicated item matrix with evidence and proposed GRC action. The desired endpoint is that GRC becomes the single current status system again, while this document remains a dated reconciliation/audit artifact.
