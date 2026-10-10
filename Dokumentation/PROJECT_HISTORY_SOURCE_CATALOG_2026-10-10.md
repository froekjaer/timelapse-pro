# TimeLapse Pro — Historical Source Catalog

**Date:** 2026-10-10  
**Status:** Review snapshot; not an authoritative status register  
**Purpose:** Catalogue the sources that must be reconciled before importing/updating status in GRC.

## Authority rule

This catalogue does not create a new source of truth. The repository states that from 2026-07-16 the PostgreSQL GRC tables `grc_items`, `grc_links`, `grc_test_runs`, and `grc_evidence` are the authoritative GRC status source. Historical documents are evidence and discovery sources. Later implementation/verification evidence may supersede their status statements.

## A. Primary reconciliation / closure sources

- `MASTER_REVIEW_CLOSURE_2026-08-15.md` — authoritative closure ledger at its recorded baseline; strict OPEN→FIX→MERGED→VERIFIED→CLOSED vocabulary.
- `Assessment_2026-07_3P_RECONCILIATION_2026-08-25.md` — reconciles the July independent assessment against later architecture.
- `CONVERGENCE_SOURCE_TO_DECISION_TRACEABILITY_2026-08.md` — convergence traceability.
- `TIMELAPSE_PRO_RELEASE_CONVERGENCE_PLAN_2026-08.md` and locked architecture decisions.
- `PAKKE_SPOR_REGISTER.md` — package/workstream register.
- `HANDOVER_LOG.md` plus archived/pre-rotation handovers — chronological operational/project evidence.
- Capability register proposal/final proposal and capability-map work (including open PR #243).

## B. GRC / assurance sources

- `VERIFICATION_RISK_EVIDENCE_REGISTER_v1.md` — migration source/report format; explicitly delegates authoritative status to PostgreSQL GRC from 2026-07-16.
- `KRAVREGISTER_og_STATUS_v10.md` — historical requirement inventory; status figures are not current without reconciliation.
- `RISK_ASSESSMENT_v10.md`, v11/v12 addenda.
- `GO_LIVE_CHECKLIST_v10.md`.
- `SYSTEM_HEALTH_REGISTER.md`.
- `Compliance-Readiness-Pack/` — DPIA, processing roles, vulnerability/update SLA, SBOM evidence, ISO/NIS2/CER supplier assurance, AI inventory, acceptance gate.
- `Codex-Audit/` — current-era audit package: readiness, architecture, code findings, security/risk/pentest, compliance, acceptance roadmap, evidence log.

## C. Governance / branch recovery

- `Pakke_Governance_Review_2026-09/` — frozen branch refs, screening, reviews, recovery pilot and disposition.
- `R04_BRANCHTRIAGE_BATCH_2_2026-09-13_CLAUDE.md`.
- `PAKKE_GOVERNANCE_REVIEWPAKKE_2026-09.md`.
- `Mission_Framework_Assessment/`.

## D. Historical review lineage

Preserve as evidence; do not treat old status as current:
- Claude, Codex, Kimi and z.ai reviews from June–August.
- `Gamle versioner/Assessment_2026-07_3P/`.
- `Gamle versioner/` risk/SABSA/pentest material back to May 2026.
- old requirement registers, go-live checklists, manuals, session handovers and update-flow plans.

Notable early sources include:
- `Gamle versioner/SABSA_RISK_ANALYSIS_UPDATE_2026-05-28.md`
- `Gamle versioner/VIRTUAL_PENTEST_STATUS_2026-05-28.md`
- `Gamle versioner/2026-06-03-Timelapse - Risk og plan videre.md`
- `Gamle versioner/Codex_Overtagelsesnotat_2026-06-03.md`
- `Gamle versioner/Sessionoverlevering_2026-06-23_konsolideret.md`

## E. Open PR evidence as of 2026-10-10

17 open PRs were observed during this reconciliation. They are evidence/work-in-progress, not automatically backlog truth. High-impact tracks include:
- #274 SSH access design — awaits Peter decision; must reconcile with newer tunnel/wake implementation on main.
- #259 stacked on #246 — Edge API mTLS runtime/security closure; must not be merged independently.
- #258 Apple Foundation Models/provider architecture — large draft; requires reconciliation with current main.
- #257 Golden Edge reproducibility/builder gaps.
- #256 Edge1 preservation/re-image gate.
- #253 reverse-tunnel health after network changes.
- #248 GRC consolidation with non-main base.
- #243 capability map.
- older PR tail must be checked for supersession by current main.

## F. Reconciliation method

For every unique initiative/finding/capability:
1. Preserve original source ID/title and earliest known source.
2. Link later reviews/reconciliations and GRC identity if present.
3. Check current main/code/config/tests.
4. Check merged/open PR evidence.
5. Separate implementation from verification.
6. Assign provisional state: VERIFIED COMPLETE / IMPLEMENTED-UNVERIFIED / PARTIAL / DESIGN-ONLY / OPEN / SUPERSEDED / ABANDONED / UNKNOWN.
7. Only after Peter review, prepare GRC import/update actions.
