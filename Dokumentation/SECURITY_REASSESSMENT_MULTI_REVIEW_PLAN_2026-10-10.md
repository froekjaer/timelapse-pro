# TimeLapse Pro — Security Reassessment Multi-Review Plan

**Date:** 2026-10-10
**Status:** TEST MANDATE — review before execution
**Targets:** Headend, Edge1, Edge2
**Purpose:** New independent security reassessment before external/site deployment.

## 1. Principle

Run independent assessments before reconciliation. Reviewers must not be seeded with the other reviewers' findings.

Every finding must distinguish:
- hypothesis vs demonstrated weakness;
- source/code finding vs runtime finding;
- known GRC item vs regression vs new finding;
- implementation fix vs verified closure.

No finding is CLOSED solely because code exists or a reviewer believes it is fixed.

## 2. Common scope

Assess the current deployed/releasable system, including where applicable:
- Headend application/API/UI and host configuration;
- Edge1 and Edge2 application/runtime/host configuration;
- authentication, authorization, RBAC/MFA/session handling;
- service-technician access, CLI, Edge GUI and LAB;
- SSH/reverse tunnel/wake paths and trust boundaries;
- mTLS/PKI/device identity/enrollment/revocation;
- secrets, credentials, keys and break-glass mechanisms;
- update/signing/rollback/supply-chain path;
- provisioning/Golden Edge/baseline drift;
- camera/service operations and privilege boundaries;
- tenant/site/device isolation;
- network exposure and service inventory;
- logging/audit/SIEM and evidence integrity;
- backup/restore and sensitive-data handling;
- AI components and local model/runtime attack surface;
- denial-of-service/resource exhaustion and recovery;
- physical/local attacker assumptions on Edge devices;
- historical security findings for regression.

Testing must remain non-destructive unless Peter explicitly approves a destructive test.

## 3. Test A — Codex independent offensive review

### Role
Primary adversarial security reviewer.

### Objective
Try to disprove the security assumptions of the current system and identify exploitable chains, privilege escalation, boundary bypasses, unsafe defaults, regressions and gaps between documented controls and runtime enforcement.

### Required approach
1. Recover current architecture and trust boundaries from code/config first.
2. Enumerate attack surfaces on Headend, Edge1 and Edge2.
3. Review current code paths for authentication/authorization and command execution.
4. Review network/tunnel/mTLS/SSH/device-auth paths.
5. Review update/provisioning/supply-chain and rollback paths.
6. Review secrets and persistence.
7. Exercise safe runtime tests where access/evidence permits.
8. Attempt multi-step attack chains, not only isolated lint-style findings.
9. Compare findings to historical security IDs/GRC only after independent discovery.
10. Produce reproducible evidence and remediation acceptance tests.

### Deliverables
- executive risk summary;
- attack-surface/trust-boundary map;
- finding register with severity, exploit preconditions and evidence;
- attack-chain scenarios;
- Headend/Edge1/Edge2 runtime observations;
- known/new/regression classification;
- recommended remediation;
- exact verification/closure test per finding;
- unresolved questions and tests requiring Peter/physical access.

## 4. Test B — Claude independent architecture + runtime security review

### Role
Independent defensive/architecture reviewer with project-history context.

### Objective
Determine whether the implemented system still satisfies its intended security architecture and whether controls are consistently enforced across code, configuration and deployed Edge/Headend runtime.

### Required approach
1. Reconstruct intended security architecture independently.
2. Check architecture drift against current implementation.
3. Review privilege boundaries and common service-operation abstractions.
4. Review configuration inheritance and enforcement at global/customer/site/Edge/camera layers.
5. Review technician CLI/UI/LAB security consistency.
6. Review Edge baseline, SSH, tunnel, wake, PKI/mTLS and update controls.
7. Review operational failure modes, logging, recovery and evidence.
8. Review historical findings for incomplete closure or regression only after current-state assessment.
9. Identify security debt caused by duplicated or partially converged architecture.
10. Define acceptance evidence for every claimed control.

### Deliverables
- architecture/security-control assessment;
- drift and inconsistency register;
- runtime/configuration verification matrix;
- findings with evidence and severity;
- historical-control regression map;
- remediation priorities;
- acceptance tests and evidence requirements;
- deployment blockers.

## 5. Optional Test C — Z.ai adversarial challenge

Use Z.ai as a deliberately independent challenger after Tests A and B are frozen, but before final reconciliation.

Focus:
- challenge assumptions shared by Codex and Claude;
- seek overlooked attack chains and unusual boundary crossings;
- test whether proposed remediations actually close the attack;
- identify false confidence from documentation or test coverage.

Z.ai should receive the system evidence and frozen findings, but be instructed to challenge rather than summarize them.

## 6. Optional Test D — Kimi evidence/coverage audit

Use Kimi primarily as an evidence and completeness auditor.

Focus:
- trace each finding/control to code, runtime evidence, historical source and GRC;
- identify contradictory statuses and missing evidence;
- find historical security requirements that disappeared from current tracking;
- check whether Headend, Edge1 and Edge2 were all actually covered;
- flag conclusions based on inference rather than executed tests.

Kimi should not be treated as the primary penetration tester; its value here is independent breadth and reconciliation pressure.

## 7. Final reconciliation

After independent reviews are frozen, ChatGPT reconciles them into one register.

For every deduplicated item record:
- reviewer/source;
- affected component(s);
- severity;
- exploitability/preconditions;
- evidence;
- existing GRC ID/link if any;
- historical finding relationship;
- current implementation state;
- current verification state;
- conflict between reviewers;
- proposed remediation;
- required closure evidence;
- proposed GRC action.

Classification:
- NEW
- KNOWN / STILL OPEN
- KNOWN / MITIGATED BUT UNVERIFIED
- REGRESSION
- DUPLICATE
- SUPERSEDED
- FALSE POSITIVE / NOT REPRODUCED
- VERIFIED CLOSED

## 8. Deployment gate

Before placing a camera/Edge at an external site, explicitly review:
1. critical/high security findings;
2. remote camera-control verification;
3. remote recovery/technician access;
4. update + rollback;
5. identity/tunnel/mTLS/SSH controls;
6. backup/restore and operational recovery;
7. unresolved physical/runtime tests.

The final go/no-go must be based on evidence from the deployed/release candidate state, not documentation alone.
