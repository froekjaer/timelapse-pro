# TimeLapse Pro — Independent Deep Review, evidence checkpoint

**Date:** 2026-10-10  
**Reviewer:** ChatGPT  
**Status:** DOCUMENT REVIEW / preliminary evidence reconciliation — NOT a live penetration test or verified deployment audit.

## Sources reviewed

- `Dokumentation/Codex-Audit/05_SECURITY_RISK_SABSA_PENTEST.md`: historic non-destructive virtual pentest explicitly states *no live exploitation was attempted*; findings CA-001 through CA-008 require current-state revalidation.
- `Dokumentation/Codex-Audit/06_COMPLIANCE_ASSESSMENTS.md`: readiness-oriented assessment; not clause-complete or certification.
- `Dokumentation/Codex-Audit/07_ACCEPTANCE_GATE_AND_ROADMAP.md`: signed artifact, host identity, technician grant, rollback, restore and privacy gates.
- `Dokumentation/HANDOVER_LOG.md`, entries 2026-10-05 and 2026-10-10: physical LAB wake and NPU shadow-mode observations; simulated LAB progress UI.
- Open PRs #257 (Golden Edge), #259 / #246 (mTLS), #274 (SSH design), #258 (Apple Foundation Models), #248 (GRC requirements), #243 (capabilities), #245 (control-plane versus runtime outcome).
- Issues #295 and #296 contain independent review mandates. Their existence does NOT prove Codex or Claude are running.

## Critical observations and verification backlog

| Priority | Track | Documented basis | Actual verification needed |
|---|---|---|---|
| P0 | Golden Edge reproducibility | PR #257 describes image-builder gaps including Wi-Fi, time sync, watchdog, TOTP requirements and relay rule | Fresh artifact, clean installation, hardware boot and end-to-end validation; compare device baseline |
| P0 | Remote camera control | User's critical acceptance need; previous handovers report CLI/GUI/LAB capabilities | Actual camera response for manual focus, one-shot AF, zoom where supported, ISO, WB, shutter; confirm correct command route, resulting parameter and image quality |
| P0 | Edge identity and mTLS | PR #259 explicitly excludes production CA ceremony, physical enrollment and nginx mTLS enforcement; stacked on #246 | Validate each deployed Headend/Edge device identity, auth, revocation and actual enforcement |
| P0 | Signed update / rollback | Earlier acceptance gate explicitly prohibits unsupported deployment | Release signature and hash, preservation of device data/credentials, remote non-destructive rollback evidence |
| P0 | Security assessment | Historic virtual pentest was manual without live exploitation | Independent source reviews, safe lab tests, separately approved runtime/physical exercises |
| P1 | Historic CA-001..CA-008 | August Codex audit includes SQL, SSH host key, legacy access, restore, auth, key issuance, SFTP trust, test isolation | Recheck one by one against current main and actual deployed release; do not assume unresolved or fixed |
| P1 | Unified service operations | Intended common CLI, GUI and LAB command foundation | Trace shared authorization/service interfaces and test each UI path |
| P1 | LAB wake | Oct 10 handover reports live SSH tunnel wakes on both Edges in ~2–4s, and LAB start warm-up improvements | Pin deployed versions and independently repeat measurement |
| P1 | LAB progress display | Oct 10 handover reports simulated-preview UI test | Real Edge end-to-end display and failure-path test |
| P1 | Edge NPU image quality | Oct 5/10 handover reports both Edge devices in **shadow** mode | Verify model artifacts, scored captures, CPU comparison, false alarms and whether outcomes affect decisions |
| P1 | Daily consistency and white balance | UI denotes features disabled/not implemented per user | Locate exact UI labels, requirements/design, code status and acceptance tests |
| P1 | Apple Foundation Models | PR #258 describes physical POC and native image provider route | Representative comparative benchmark accuracy, latency, resources and privacy |
| P1 | Complete GRC and compliance | PR #248 describes 121 reviewed product requirements | Separate those from exhaustive ISO/IEC/EU legal requirement population; evidence-backed applicability + per-requirement outcome |
| P2 | Historical reconciliation | GitHub, archived handovers and pre-GitHub Drive history | Chronological source index, supersession links, canonical GRC mapping |

## Review principles

- **Architecture ≠ code ≠ green CI ≠ deployed ≠ runtime verified ≠ capability verified.**
- Record evidence provenance with source path, commit SHA, release, device, timestamp, test procedure and observed result.
- Never infer a security finding is closed from a PR, code comment or a handover note alone.
- The prior eight CA findings are **historical candidates** requiring current verification; do not blindly repeat their old severities.
- PR #243's capability maturity approach is a good working model; keep it separate from normative compliance maturity.
- PR #248's reviewed product requirements are **not** equivalent to a complete standards requirement catalog.
- No production changes, GRC closures or external compliance claims until reviewed and supported with verifiable evidence.

## Proposed next ordered steps

1. Build main / branch / release / device evidence matrix and resolve conflicts between PR descriptions and Oct 10 handovers.
2. Verify clean Golden Edge installation and remote camera operation before placing a camera at an unattended site.
3. Run approved independent security tests, including safe runtime tests, and revalidate historical CA findings.
4. Reconcile results with existing GRC and project capability register without creating an authoritative competing status database.
5. Conduct full-population compliance mapping using legally accessible normative texts and documented N/A justifications.

**This document records review observations and a test backlog; it does not claim technical or legal compliance.**
