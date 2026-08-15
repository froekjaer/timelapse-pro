# Edge Runtime Convergence Plan — 2026-08

Status: read-only recovery and convergence plan after WP-4. No Edge deployment has been performed.

Authority:

- Headend stays on `bc367d4dc328dea6bc22aa71bcbc887d89c577c8`.
- WP-4 target remains: generic signed Edge image, signed provisioning envelope, Edge-owned SSH/TLS private keys, Trust Service lifecycle authority, explicit legacy migration adapters.
- Existing Edges must converge without reprovisioning, destructive key rotation, credential deletion, GPIO mapping changes, SSH trust bypass or remote lockout.

## Evidence Bundles

Headend evidence:

- `/Volumes/data-fast/peter-home/projects/timelapse-pro-edge-recovery/20260815_163111_HEADEND/headend_runtime_evidence.txt`

Edge 1 evidence and backup:

- Device: `TL-C87FF9587CA0`
- IP: `192.168.86.134`
- Evidence directory: `/Volumes/data-fast/peter-home/projects/timelapse-pro-edge-recovery/20260815_163111_TL-C87FF9587CA0`
- Runtime/config/unit/state backup: `runtime_config_units_state.tar.gz`
- Capture manifest only: `captures_manifest.txt`
- Backup hashes: `SHA256SUMS.txt`

Edge 2 evidence:

- Device: `TL-043EB9E72EFD`
- IP: `192.168.86.117`
- Evidence directory: `/Volumes/data-fast/peter-home/projects/timelapse-pro-edge-recovery/20260815_163111_EDGE2_TL-043EB9E72EFD`
- Trusted Headend/API evidence: `headend_trusted_evidence.txt`
- Current unauthenticated SSH keyscan: `current_ssh_keyscan.pub`
- Existing local known_hosts evidence: `known_hosts_entries.txt`, `known_hosts_fingerprints.txt`
- Recent Headend telemetry/log signals: `headend_recent_edge2_signals.txt`

## Current Runtime Summary

### Headend

- Deployment commit: `bc367d4dc328dea6bc22aa71bcbc887d89c577c8`
- Health: Headend API and Edge authenticated API were verified after v29/v30 migration reconciliation.
- Constraint: no rollback. This commit is the release anchor for Edge convergence.

### Edge 1 — `TL-C87FF9587CA0`

- SSH trust: existing SSH path works.
- Hostname: `timelapse0101`
- OS: Ubuntu 24.04.4 LTS, arm64.
- Runtime release receipt: `v2.8.1-lab.28`, source commit `b25703ed6942c9b013293fc6d6f84f637f795201`.
- `/opt/timelapse` git checkout: `bf8b27709882bbb333bbcc1aabbd90734fc222da`, behind `origin/main` by 12 commits.
- Working tree: dirty, with 28 modified tracked files and 130 untracked paths.
- Runtime health from read-only checks: `timelapse-edge`, local technician services, time sync and watchdog services were active.
- Recent capture/upload: Headend observed successful capture and upload from Edge 1 on 2026-08-15.
- Duplicate capture check: no duplicate minute slots were observed in the recent two-hour Headend query.

### Edge 2 — `TL-043EB9E72EFD`

- SSH trust: blocked by host-key mismatch. Treat as a security event.
- Trusted Headend identity: device is online, last_seen was fresh during evidence collection, IP `192.168.86.117`, hardware model `orangepi4pro`, app version `2.8.0`, enrollment state `active`.
- Credential state: active legacy `device_api` credential in `edge_credential_inventory`, sourced from `devices.api_token` through the legacy migration adapter.
- Reverse tunnel telemetry: reverse tunnel has connected historically, including on 2026-08-15.
- Camera telemetry: repeated `camera_detection_failed`; the relay was turned on by the normal capture process, `gphoto2 --auto-detect` returned no camera, and the relay was turned off again.
- Capture state: no recent successful capture was observed after 2026-08-14 20:30:01.
- Constraint: do not edit `known_hosts`, disable host verification, accept a new SSH host key, perform relay/power actions, or deploy software until SSH identity is verified through a trusted channel or local/physical confirmation.

## Edge 1 Source Change Classification

### Modified tracked files already identical to current main

Classification: historical hotfix now absorbed in main.

- `edge/ai/SITE_LOOK_MATCHING.md`
- `edge/ai/autonomous_optimizer.py`
- `edge/ai/npu_quality.py`
- `edge/ai/site_look_config_client.py`
- `edge/ai/site_look_manager.py`
- `edge/camera/drivers/gphoto2_driver.py`
- `edge/config/bt-config.yaml`
- `edge/config/manager.py`
- `edge/config/site_look_config.example.yaml`
- `edge/diagnostics/camera_diagnostics.py`
- `edge/frame_push.py`
- `edge/scripts/bootstrap_agent.py`
- `edge/scripts/deploy-totp.sh`
- `edge/scripts/gen-bt-cert.sh`
- `edge/scripts/setup-gps-time.sh`
- `edge/scripts/sync-time.sh`
- `edge/scripts/timelapse-bt-pan.sh`
- `edge/scripts/timelapse-captive.sh`
- `edge/scripts/timelapse-edge.service`
- `edge/scripts/timelapse-timesync.service`
- `edge/technician_ui.py`
- `edge/upload/sftp.py`
- `edge/utils/inventory.py`

### Modified tracked files that differ from current main

Classification: source changes that must not be carried forward automatically.

| Path | Classification | Current assessment |
| --- | --- | --- |
| `edge/agent.py` | obsolete/stale plus historical WIP | Edge local code contains an older scheduler fix and break-glass forwarding traces. Current main contains PR #16 scheduled-slot handling and WP-3 Service Operations integration. Main is the target. |
| `edge/capture/buffer.py` | historical hotfix / policy conflict | Edge local code contains confirmed-uploaded circular deletion with `deleted_at`. Current main keeps safer capacity-guard behavior. Do not merge without an explicit retention/deletion business decision. |
| `edge/scripts/totp-service.py` | obsolete/stale | Edge local code contains older shell/xterm/browser-terminal style behavior and lacks current main ServicePlatform invalidation behavior. Main is the target. |
| `edge/tools/bootstrap_cli.py` | obsolete/stale | Edge local code lacks current main WP-3 service-operation, commissioning and technician status parity. Main is the target. |
| `edge/utils/database.py` | stale except optional deletion-policy state | Edge local code contains `deleted_at` support for circular deletion but lacks current main `capture_slots`. Main is required for scheduler correctness. |

Conclusion: no focused PR is required before Edge 1 convergence. The only Edge-local source behavior missing from main is either explicitly out of current scope or a separate retention-policy decision.

### Untracked path groups

| Path group | Classification | Handling |
| --- | --- | --- |
| `edge/.timelapse-release.json` | legitimate device/runtime configuration | Preserve on Edge and include in rollback evidence. |
| `edge/keys/edge_signing_ed25519.pem*` | legitimate device credential material | Preserve only in runtime backup and on Edge. Do not copy into repo or replace destructively. |
| `edge/.last_backup_request`, `edge/siem_journal.cursor`, `edge/.qa/*` | generated/runtime state | Preserve in backup; do not migrate into release source. |
| `models/edge_qa*`, `bin/edge_qa_viplite*` | generated/runtime/model artifacts | Preserve if still used locally; do not migrate into release source. |
| `edge/agent.py.bak*`, `edge/camera/drivers/*.bak`, `edge/camera/drivers/*.orig`, `edge/upload/*.bak*` | obsolete/stale local backups | Preserve in snapshot only; exclude from release deployment. |
| `edge/scripts/breakglass*`, `edge/scripts/static/xterm/*`, `edge/scripts/timelapse-breakglass*` | historical WIP/out-of-scope | Preserve in snapshot only. Do not enable as normal technician feature. |
| `edge/scripts/timelapse-watchdog.service` | historical hotfix candidate | Compare to current service model before any reuse. Preserve in snapshot. |
| `edge/camera/live_video.py`, `edge/camera/maintenance.py`, `edge/camera/service_stream.py`, `edge/camera/technician_session.py` | historical local service WIP | Superseded by WP-3 ServicePlatform baseline unless a future targeted diff proves otherwise. |
| `prev/edge/**` | historical recovery snapshot | Preserve in backup only. |

## Edge 1 Non-Destructive Convergence Procedure

Do not upgrade by running `git pull`, `git reset` or direct source overwrite inside the dirty `/opt/timelapse` checkout.

1. Keep the current runtime active until a side-by-side release and rollback path are proven.
2. Verify backup readability before any change:
   - confirm `SHA256SUMS.txt`
   - list `runtime_config_units_state.tar.gz`
   - confirm `/data/timelapse_edge.db`, `/opt/timelapse`, `/etc/timelapse` and systemd units are present in the archive
3. Build or select the immutable release artifact from Headend commit `bc367d4dc328dea6bc22aa71bcbc887d89c577c8`.
4. Run read-only Edge preflight:
   - service health
   - Headend API authentication
   - capture DB integrity
   - free disk and inode headroom
   - image backlog
   - config file presence and hashes
   - credential file presence and permissions
   - GPIO mapping snapshot
   - current systemd unit hashes
5. Stage the new release side-by-side, for example under `/opt/timelapse/releases/bc367d4dc328dea6bc22aa71bcbc887d89c577c8`, without modifying `/data`, `/etc/timelapse` or existing credential paths.
6. Bind the staged release to existing preserved runtime state:
   - `/data`
   - `/data/timelapse_edge.db`
   - `/opt/timelapse/edge/config.yaml`
   - `/opt/timelapse/edge/bootstrap.yaml`
   - `/opt/timelapse/edge/sftp_cache.yaml`
   - existing API token file
   - existing Edge key directories
   - existing SSH/TLS material
   - existing GPIO mapping
7. Dry-run service start commands where possible without replacing active services.
8. Switch atomically by service/symlink only after preflight passes.
9. Verify after switch:
   - agent/service health
   - Headend authentication/connectivity
   - capture scheduler uses scheduled slots
   - exactly one capture attempt per scheduled slot
   - upload path
   - camera detect/PTP
   - modem/network
   - storage/backlog
   - Service Operations technician status
   - certificate/trust status
   - reboot/reconnect
10. Roll back by switching the service pointer back to the previous runtime and restoring units/config from the backup if needed. Do not delete credentials or rotate keys during rollback.

## Edge 2 SSH Host-Key Security Procedure

The current SSH server host keys observed through keyscan do not match the trusted `known_hosts` entries. The current keyscan is not authenticated and must not be trusted by itself.

Known trusted local fingerprints for `192.168.86.117`:

- ED25519 `SHA256:RRlbGT476NFcVCLdixp27pU8SVaS0AJjYcC7NxWRo+8`
- RSA `SHA256:suKTGEeXEyzYxg9zvXSffJbUrHNdUWwBGOE7u+PSMlg`
- ECDSA `SHA256:OjTccGhCQXxM5Or89donvkXEjb8YB1oRORtSysPPVzY`

Current unauthenticated keyscan:

- ED25519 `SHA256:cEHcetG6VrsTKZklL5H2u0TPqKl03RuJIAhJWfu0sZ0`
- RSA `SHA256:wXM+Dt7jkJ++3brAMIMP7tYi9ZRVwdIxOLqROPZ4jbU`
- ECDSA `SHA256:IOCh49GoZKfpelAmjfgUNnrYJpvElW05+pRB6yrYh9w`

Required verification before SSH can be used:

1. Use an already trusted Headend/API/Service Operations channel to ask the Edge to report `/etc/ssh/ssh_host_*_key.pub` fingerprints and host-key generation timestamps.
2. Compare reported fingerprints against provisioning history, audit records, backups or previous trusted snapshots.
3. If no trusted remote evidence exists, require local console, physical inspection or explicit owner confirmation before accepting a new SSH host key.
4. Only after verification may `known_hosts` be updated with the verified host key.

Until this completes:

- no SSH login
- no known_hosts edit
- no host verification bypass
- no software deployment
- no credential/key rotation

## Edge 2 Camera Failure Read-Only Procedure

Current trusted telemetry indicates Headend/API connectivity is alive, while camera detection is failing.

Observed pattern:

- normal capture cycle turns camera relay on
- warm-up completes
- `gphoto2 --auto-detect` reports no camera after retries
- relay turns off again
- Headend logs `camera_detection_failed`
- last successful capture observed: 2026-08-14 20:30:01

Read-only next steps:

1. Continue collecting Headend/API telemetry for relay history, capture attempts, camera detection failures and upload status.
2. Confirm whether failures began after OS update attempts, reboot, USB bus changes or service restarts.
3. Compare reverse tunnel, device API, lifecycle and credential telemetry to rule out identity/auth failure.
4. Do not issue relay, power-cycle, reboot, USB reset or camera reconnect commands remotely while SSH trust is unresolved.
5. After SSH identity is verified, run read-only local diagnostics first: USB device list, gphoto/PTP detect, kernel USB errors, camera battery/power state if available, storage, system load and service logs.

## Common Upgrade Safety Rules

- Upgrade one Edge at a time.
- Do not reprovision existing Edges.
- Do not delete, overwrite or rotate existing credentials during convergence.
- Do not change GPIO/relay mapping.
- Preserve capture DB, images, config, credentials, device identity and site assignment.
- Keep legacy migration adapters until the new credential path is verified active on each Edge.
- Do not use browser shell/terminal as a normal technician feature.
- Do not start generator UI redesign, CSR/PKI redesign or new service features in this recovery slice.

## Exit Gate Before Any Edge Deployment

Edge deployment may start only when all of the following are true:

- Headend is stable on `bc367d4dc328dea6bc22aa71bcbc887d89c577c8`.
- Edge 1 backup hash and archive readability are verified.
- Edge 1 rollback path has been rehearsed without touching live credentials.
- Edge 1 staged release plan preserves runtime state and uses current main as source.
- Edge 2 SSH host-key mismatch is resolved through trusted evidence or physical confirmation.
- Edge 2 camera failure is understood enough that remote work will not increase lockout risk.
- Only one Edge is selected as canary.

## Remaining Risks

- Edge 1 has a dirty runtime checkout with old local service and scheduler code; direct git-based upgrade would be risky.
- Edge 1's local confirmed-uploaded deletion behavior is not in current main and needs a separate product/retention decision before any future reintroduction.
- Edge 2's SSH server identity is unverified. Accepting the new key without corroboration would bypass host trust.
- Edge 2 has a real camera-detection fault while owner is away; remote power/relay actions should stay blocked until identity and recovery options are clear.
