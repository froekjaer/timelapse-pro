# TimeLapse Pro — Initial Reconciliation Priority Register
Date: 2026-10-10. Status: CANDIDATES; NOT LIVE-VERIFIED. Sources: user review, earlier Codex-Audit, security reassessment plan. Do not infer completion.

| Priority | Candidate | Known basis | Evidence still needed |
|---|---|---|---|
| P0 | Remote camera focus, autofocus, zoom, ISO, shutter, white balance | CLI/GUI/LAB reportedly expose controls; handover notes code work | Test each control end-to-end on actual camera via remote path; record hardware capability, permission, command and image result |
| P0 | Security of Headend, Edge1, Edge2 | Historical virtual pentest and CA-001..CA-008 | New independent source, lab and approved runtime testing |
| P0 | Edge identity, technician grants, mTLS, SSH, reverse tunnel | Historical risk register and open PR #246/#259 | Current main and deployed runtime verification |
| P0 | Signed update, rollback, recovery | Earlier acceptance gates | Signed artifacts and successful rollback/recovery on real devices |
| P1 | Shared service operations across CLI, GUI, LAB | WP3 / handover design intent | Trace architecture, implementation and authorization consistency |
| P1 | Site-wide image consistency and daily white balance stabilization | UI shows disabled/not implemented per owner | Confirm UI feature flags, architecture, code and GRC |
| P1 | Edge AI image assessment and sharpness measurement | Existing experiments and modules reported | Trace image pipeline, test actual results |
| P1 | Apple Foundation Models vs other AI providers | Experimental work reported | Benchmark accuracy, latency, energy, privacy, cost on representative image set |
| P1 | Backup/restore rehearsal | Historical audit gap | Real recovery evidence and measured RTO/RPO |
| P1 | Full-population compliance audit | Previous readiness assessments only | Actual Compliance UI inventory, licensed normative requirements and evidence-backed clause mapping |
| P2 | Project history reconciliation | Historical material may predate GitHub (March/April 2026), Drive, handovers | Source index, deduplication and GRC links |

## Status scheme
IDEA / ARCHITECTURE / CODE PARTIAL / CODE COMPLETE UNVERIFIED / VERIFIED / SUPERSEDED / UNKNOWN. Separate scope and implementation from test result. Preserve every candidate even when not yet found in code.

## Review sequence
Security mandate first; independent reports; reconcile and rank actionable issues. Then full-population compliance. Finally propose GRC updates for owner review, with no automatic closures.
