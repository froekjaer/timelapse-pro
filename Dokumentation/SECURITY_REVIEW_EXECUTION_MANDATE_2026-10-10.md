# TimeLapse Pro — Security Review Execution Mandate
Date: 2026-10-10. Status: PLANNED, NOT EXECUTED. Targets: Headend, Edge1, Edge2.

## Evidence baseline
Reuse Dokumentation/Codex-Audit/05_SECURITY_RISK_SABSA_PENTEST.md, 07_ACCEPTANCE_GATE_AND_ROADMAP.md, the existing multi-review plan, GRC and handover history. Earlier "virtual pentest" explicitly says manual, non-destructive and no live exploitation. Do not label it a completed penetration test.

## Test A — Codex independent code + adversarial review
1. Pin exact main/PR commit hashes and inventory exposed APIs, SSH, SFTP, tunnels, browser terminal, CLI/GUI/LAB, mTLS, enrollment, updates, AI runtime and dependencies.
2. Map trust boundaries and attack hypotheses; use SAST, dependency and secrets scans, auth coverage tests and safe negative tests where execution is possible.
3. Review CA-001 through CA-008 as historical hypotheses, not assumed current vulnerabilities.
4. Report each issue with component, reproduction steps (safe), preconditions, impact, CVSS if defensible, evidence, commit, remediation, regression test and GRC linkage.
5. Do not perform destructive exploitation or change production state without explicit approval.

## Test B — Claude independent architecture + runtime assurance
1. Independently reconstruct intended controls, SABSA attributes and deployed topology.
2. Compare documented controls with current code and observed runtime, distinguishing Headend, Edge1 and Edge2.
3. Verify common service-operations authorization for CLI/GUI/LAB and camera controls.
4. Evaluate SSH identity, host-key rotation, technician grants, RBAC/MFA, secrets, signed updates, rollback, recovery and logging.
5. Produce independent finding register and evidence gaps before reading Codex conclusions.

## Third-party challenge
Z.ai challenges frozen findings and tests bypass scenarios; Kimi audits historical coverage, missing evidence and GRC mapping. No model's unsupported opinion counts as runtime proof.

## Execution boundaries
Phase 0 read-only discovery and configuration snapshots; Phase 1 source/CI/isolated lab tests; Phase 2 approved safe authenticated runtime tests; Phase 3 separate physical device tests. Never assume network access or device credentials exist. Record explicit NOT TESTED wherever unavailable.

## Exit criteria
Separate vulnerability status from implementation and verification; deduplicate with GRC only after independent reports; maintain open issues until fixes and regression tests verified; gate site deployment on high-risk items, remote camera control, recovery, update and trust-path verification.
