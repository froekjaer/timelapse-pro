# Headend–Edge boundaries and current-main delta — 2026-10-10

**Scope:** Preliminary source-level comparison. No production code modified, no runtime tests executed. Non-regression mandatory.

## Architecture rule: separate ownership

| Concern | Headend owns | Edge owns | Interface contract |
|---|---|---|---|
| Camera | Scheduling policy, site/customer association, remote requested operation, UI authorization | Physical gphoto2/PTP, lens/focus/ISO/WB/shutter execution, relay control and safe teardown | Versioned typed CameraOperation request, accepted/executed/failed outcome with device/camera IDs, idempotency key, TTL and evidence |
| Capture | Central ingest, gallery, long-term storage, retention policy | Offline capture scheduling, local durable queue, local image metadata | Capture manifest and immutable IDs, timestamp UTC plus timezone/provenance |
| Update | Signed artifact publishing, approval, staged rollout, per-target outcome tracking | Signature verification, install, durable receipt, independent rollback/watchdog | UpdatePlan, artifact identity, health evidence, state machine and terminal outcome |
| Remote access | User MFA, grant issuance, tunnel visibility, host trust approval, audit | SSH daemon, local TOTP portal, root recovery terminal, expiry enforcement and local recovery | Explicit grant/capability/session contract; never infer permission from tunnel connectivity |
| AI | Provider selection, policy, cloud/local routing, central provenance and user review | Optional NPU/CPU on-device quality observations; capture stays autonomous | Versioned QualityObservation (shadow/active explicit), model/provenance, no hidden promotion to authority |
| Configuration | Global/customer/site/camera inheritance and effective configuration | Validated applied local config, overrides and hardware-specific adaptation | Signed/versioned effective config, ack/nack, last-applied and rollback |
| GRC | Evidence index, requirements, risks, compliance reports | Device attestations and factual runtime evidence only | Signed/auditable evidence records, no Edge-local competing GRC authority |

## Main vs PR direct observations

1. `headend/tools/golden_edge_baseline.py` is absent on main (404); `headend/tools/build_edge_disk_image.py` exists and does not contain `golden_edge_baseline`. PR #257 adds a baseline validator. **Unintegrated at those paths**, not proof no equivalent elsewhere.
2. `edge/update_lifecycle.py` exists on main and contains a durable pending-update receipt/recovery path and a `health_timeout_s=180` argument. Search in retrieved file found no `stability` string; PR #163 proposes a post-restart stability window and Headend sweeper. **Do not replace current recovery**; semantic diff of behavior required.
3. `headend/services/post_restart_health.py` is absent on main (404); PR #163 introduces it. This is a concrete file-level integration gap, not evidence that all health sweeping is absent elsewhere.
4. `edge/scripts/totp-service.py` exists on main with a local TOTP management portal and PTY support. PR #239 adds xterm terminal assets and regression tests. Preserve existing root recovery behavior under ADR-004.
5. `headend/api/ssh_tunnel_terminal_api.py` exists on main and already implements controlled browser SSH terminal with `edge.shell.remote` capability and host-key trust lookup. PR #253 changes that path; reconcile rather than duplicating terminal endpoints.
6. #246→#259 mTLS are stacked; do not conflate transport authentication, authorization and technician UI access.
7. #258 AI routing must remain Headend policy; Edge NPU quality scoring remains separately identified as shadow until validated and approved.
8. #159 capture timestamp should use a shared contract; Edge records acquisition instant, Headend preserves and UI formats it.

## Proposed typed API boundaries (design candidates, not implemented)

- `CameraOperationRequest{schema_version,request_id,device_id,camera_id,operation,parameters,deadline,principal_grant}` → `CameraOperationResult{request_id,status,observed_state,error_code,executed_at,evidence_ref}`.
- `UpdatePlan{schema_version,artifact_id,source_commit,signature,targets,maintenance_window,rollback_policy}` → `UpdateOutcome{device_id,artifact_id,phase,health_evidence,rollback_receipt}`.
- `QualityObservation{capture_id,engine,model_version,mode,score,threshold,provenance}` with `mode=shadow|active` explicitly visible.
- `EffectiveConfig{version,scope,provenance,settings,signature}` → `ConfigApplyReceipt{version,device_id,applied_at,status,errors}`.
- `AccessGrant{principal,device_id,capability,expires_at,session_id,step_up_evidence}` and audited session outcome.

These are boundary definitions for review, not an instruction to refactor all services now. Existing interfaces remain supported until adapters, compatibility tests and physical acceptance prove equivalence.

## Immediate next source-level verification
- Read full #257 validator and builder patch and compare with current builder, Dockerfile, target and dependency manifests.
- Read #163 post-restart health and sweeper code, compare against main health/update state machine.
- Trace #239/#253/#246/#259 auth/terminal/tunnel from UI→Headend→Edge, including local recovery when Headend is offline.
- Build per-operation tests verifying Edge-local autonomy, stable contracts, authorization, idempotency, timeout and rollback.

**No removal, merge, deployment or closure authorized by this document.**
