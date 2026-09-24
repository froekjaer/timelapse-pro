# Edge1 preservation / re-image gate — 2026-09-24

**Status:** `BLOCKED`  
**Scope:** preservation before any possible Edge1 re-image  
**Frozen source baseline:** `origin/main` `b901d486733d69733bad2f21dfa42354573b6aba`  
**Physical observations:** 2026-09-24 23:25–23:29 CEST via existing reverse SSH tunnels  
**Safety:** Edge1 and Edge2 were strictly read-only. No service, package, config, permission, certificate, update or image state was changed.

## Decision

Edge1 must not be re-imaged yet. Current main does not provide a complete, evidenced path from ISO Builder through first boot/provisioning to the product-required runtime state observed on Edge1. The concrete blockers are:

1. **Time synchronisation is not reproduced by current main's image path.** `timelapse-timesync.service` and `.timer` exist in source and on Edge1, but `Dockerfile.edge` does not copy them into the image and the injector does not install/enable them. Edge1's timer is enabled and active; its service is enabled and runs on demand.
2. **The TimeLapse watchdog is not reproduced by current main.** Edge1 has an enabled and active `timelapse-watchdog.service`. Current main has `watchdog.sh`, but no source unit and no Builder/injector installation path for the unit.
3. **The Golden Edge package/config baseline is not deterministic in current main.** Both physical edges rely on NetworkManager and chrony. Current `Dockerfile.edge` and the Orange Pi target package list do not declare either one. Their presence can therefore depend on the chosen vendor base image rather than the product build contract.
4. **No accepted fresh-image runtime evidence closes the full capability chain.** Both physical edges currently report the Wi-Fi AP fallback failed, already tracked as open P0 `FIND-EDGE-WIFI-AP-FALLBACK-NONFUNCTIONAL-20260924`. Edge2's timesync service is also failed. A source-file presence check cannot prove reboot, power-loss, AP fallback, GPS/NTP fallback and recovery behavior.
5. **Per-device reprovisioning has not yet been exercised as a recovery procedure for Edge1.** The injector has paths for unique SSH identity, management TLS and TOTP material, but the gate found no completed dry-run/restore receipt proving that Edge1 can be rebuilt with a newly issued identity and restored assignment/config without copying the old private material.

Claude's parallel branch contains commit `af2eca61d5668041575725a25ec0aa6f9641ff80` with proposed Golden Edge fixes for packages, watchdog, GPIO, sudoers, builder contracts and baseline validation. It is useful reconciliation evidence, but it is not part of this frozen current-main baseline and is not acceptance evidence.

## Evidence and method

- OP-001 cache verification: `VERIFIED`, canonical SHA `9a1a4543`.
- Edge1: `TL-C87FF9587CA0`, tunnel port 2201, Ubuntu 24.04.4, kernel `5.15.147-sun60iw2`.
- Edge2: `TL-043EB9E72EFD`, tunnel port 2204, Ubuntu 22.04.5, same kernel family.
- Both devices report installed artifact `TL-ART-20260909-51f93baf2817`, source commit `51f93baf…`, version `v2.8.1-lab.54`.
- Sanitised inventories covered packages, venv, systemd units/timers, users/groups, public network state, mounts, relevant path metadata/hashes, public certificate metadata, cron, GPIO devices and boot-file metadata.
- Inventory SHA-256: Edge1 `caafa0486ba3e153024b490d20b7b5a94c102517c34720388b8aaf9bfdadbf68`; Edge2 `a68b8014d255960153e2f955e9123a2aa4dd9ce7845c02a89e4dcf2fd334f189`. Raw inventory remains local and is not committed because it contains operational topology and filenames.
- GRC was queried read-only. Relevant open items include the AP fallback P0, Edge1 iperf3 exposure, Edge2 rpcbind exposure, unresolved Edge1 Git credential and break-glass design action.
- The earlier security scan for the tunnel change was **not completed** because the scan tool rejected its temporary directory as non-existing/non-canonical. It was not retried or bypassed and did not block this independent read-only preservation analysis.

## Edge1-only and asymmetric delta

| Item | Edge1 | Edge2 | Source / Builder | Function | Evidence | Classification | Action |
|---|---|---|---|---|---|---|---|
| Ubuntu release | Noble 24.04.4 | Jammy 22.04.5 | Orange Pi target and Docker base describe Jammy | OS baseline | `/etc/os-release` | `UNKNOWN` | Decide and acceptance-test the canonical OS baseline before re-image. |
| `timelapse-timesync` service/timer | Installed; enabled; timer active | Installed; enabled; timer active, service failed | Source exists; current Builder does not install it | GPS/NTP time | `systemctl show/is-enabled/is-active`; Builder trace | `PRODUCT-REQUIRED` | Add deterministic image installation/enabling and pass GPS/no-GPS/reboot tests. |
| TimeLapse watchdog unit | Enabled and active | Enabled and active | Unit absent from current main; script exists | Agent recovery | systemd inventory; source search | `PRODUCT-REQUIRED` | Restore a reviewed unit to source/Builder and pass failure/reboot recovery tests. |
| NetworkManager + chrony | Installed, enabled, active | Installed, enabled, active | Not declared by current Docker/target package contract | Network and time | `dpkg-query`; target trace | `PRODUCT-REQUIRED` | Declare in the Golden Edge baseline and verify on a clean image. |
| GPIO udev rule and `gpio` group | Rule and group/member exist | Neither exists | Absent from current main; proposed in `af2eca61` | Non-root GPIO access | root metadata; `id`; source search | `SUPERSEDED` for current execution path | Agent runs as root and service technician CLI is sudo-gated, explaining why Edge2 relay can work. Keep proposed least-privilege rule as hardening; do not copy manual state blindly. |
| TimeLapse sudoers fragments | Multiple historical files, including permissive/development fragments | Only governed service technician + break-glass fragments | Injector creates governed fragments; proposed baseline adds required edge fragment | Privileged operations | root metadata; injector trace | `SECURITY-DEBT` | Recreate only reviewed Builder-owned rules. Do not migrate Edge1 fragments. |
| QR dependency | Missing from Edge1 venv | `qrcode==8.2` | Declared in current `edge/requirements.txt`; Builder installs requirements | Technician QR login | venv freeze; source trace | `SUPERSEDED` | Fresh build supplies it; do not preserve Edge1 absence. |
| Avahi | Installed/active | Missing | Current Dockerfile declares it | `.local` discovery | package/service inventory | `PRODUCT-REQUIRED` but reproducible | Verify clean-image discovery; do not copy Edge1 package state. |
| `/etc/timelapse/tls` | Present with duplicate server key/cert | Missing | Current injector uses `/etc/timelapse/certs` | Local management TLS | root metadata; injector trace | `LEGACY` | Do not migrate `/tls`; issue/inject fresh material in canonical `/certs`. |
| iperf3 listener | Listens on all interfaces | Package present but no observed 5201 listener | Not required by product build | Test throughput | `ss`; GRC `FIND-EDGE1-IPERF3-EXPOSED-ALL-INTERFACES-20260919` | `SECURITY-DEBT` | Do not migrate or enable. |
| rpcbind | Absent | Enabled/active | Not required by product build | NFS/RPC support | service inventory; GRC finding | `SECURITY-DEBT` | Do not introduce on rebuilt Edge1. |
| SSH policy | root login and password auth enabled | both disabled | Current Builder disables both | Remote administration | root `sshd -T` | `SECURITY-DEBT` | Rebuild with current hardened policy; do not migrate old policy. |
| Desktop/CUPS/Snap/Samba remnants | Extensive Noble desktop/print packages and active CUPS | Mostly absent | Not product-required | Development rig | package and unit inventory | `LAB/DEV` | Do not migrate. |
| `camera/technician_session.py` | Present as an unreferenced file | Absent | Absent current main; preserved in remote commit `6c5e3cac` | Earlier shared camera relay session concept | full-history search and reference search | `LEGACY` residual, design value preserved | Do not copy the orphan file. Reconcile commit `6c5e3cac` separately before its branch is disposed. |
| `cmdb/executor.py` | Old active-capable legacy updater implementation | Retired inert implementation matching current main | Current main intentionally retires Git/apt updater | Updates | hash/diff | `SECURITY-DEBT` / `SUPERSEDED` | Do not migrate; current signed-artifact path wins. |
| App code deltas | Older artifact plus local historical files | Older artifact with other historical deltas | Current main is newer and contains reconciled TOTP/session/tunnel changes | Edge application | hashes and file diffs | `SUPERSEDED` except named orphan above | Deploy only governed current artifacts after image acceptance. |
| Wi-Fi profiles | Several site/test SSIDs | Device-specific profiles | Image injection accepts chosen network config | Connectivity | sanitised `nmcli` names/types only | `MUST RE-PROVISION` | Recreate intended production SSID through provisioning; do not copy obsolete/test profiles wholesale. |
| Device private keys/certs/TOTP | Unique protected material | Unique protected material | Injector/bootstrap has issuance paths | Device identity/trust | existence, ownership and mode only | `MUST RE-PROVISION` | Revoke/rotate old Edge1 identity and issue fresh material. Never copy raw private keys into evidence or Git. |

## Capability reconciliation

| Capability chain | Edge1 | Edge2 | Reproducible build path on frozen main | Result |
|---|---|---|---|---|
| Bootstrap → identity → Headend enrollment | Existing identity works | Existing identity works | Code/injector path exists; clean recovery receipt absent | `BLOCKED` pending recovery rehearsal |
| Wi-Fi client → AP fallback | Client connected; AP unit active | Client connected; AP unit failed | Packages/units exist in source, but both-device P0 says behavior is non-functional | `RUNTIME TEST REQUIRED` |
| Bluetooth discovery → BLE technician → BT PAN | Units enabled/active | Units enabled/active | Docker and units cover components | Source path present; clean-image runtime acceptance still required |
| Technician UI/CLI → TOTP/auth | Port 8443 listens; QR package missing | Port 8443 listens; QR package present | Current requirements supplies QR and current main supersedes deployed code | Reproducible in source; verify after clean build |
| Nikon Z30 → camera relay → modem relay | Root agent owns GPIO; Edge1 has additional udev/group state | Root agent owns GPIO without added group/rule | Root execution explains operation; relay source is in main | No Edge1-only functional dependency proved |
| Scheduled capture → local persistence → integrity/metadata → store-forward → reconnect/backlog | Agent active; runtime state present | Agent active; runtime state present | Core code in main; data/config is device/site state | Preserve assignments/config via Headend; runtime acceptance required |
| Heartbeat/health → remote management | Agent and reverse tunnel active | Agent and reverse tunnel active | Current main plus injector provisions tunnel ownership to agent | Source path present; prior tunnel failure handled in separate PR #253 |
| GPS/time → NTP fallback | chrony/gpsd active; TimeLapse timer active | chrony/gpsd active; TimeLapse service failed | Missing image installation for TimeLapse units and undeclared chrony | `BLOCKED` |
| Watchdog → reboot recovery → power-loss recovery | TimeLapse watchdog active | TimeLapse watchdog active | Unit absent current main/Builder | `BLOCKED` |
| Disk/retention | Device-local storage mounted | Device-local storage mounted | Application paths exist; destructive recovery not rehearsed | `RUNTIME TEST REQUIRED` |
| Certificates/trust | Canonical certs plus legacy duplicate TLS path | Canonical certs | Injector supports canonical CA-issued certs | Re-provision/rotate; do not copy legacy keys |
| Break-glass | Account exists; current root metadata lacks the canonical dedicated fragment | Account and canonical fragment exist | Injector directly creates account/sudo/log structure | Source path exists; GRC design/action remains open, so acceptance required |
| Update | Deployed old legacy executor remains on disk | Retired executor matches current main | Signed artifact path is current authority | Do not preserve legacy updater |
| Diagnostics/logging/audit | Runtime logs/cursors present | Runtime logs/cursors present | Main contains collectors; runtime-generated cursors are not image inputs | Preserve only required audit evidence under retention policy |

## Preservation manifest

### MUST RE-PROVISION

- Edge1 device identity through the authoritative Headend workflow: new/reissued SSH tunnel identity, local-management TLS certificate/key and TOTP material.
- Intended Wi-Fi network profile and AP fallback configuration through image/provisioning inputs.
- Device/customer/site/camera assignment and effective configuration from Headend, followed by a read-back comparison.
- Technician and break-glass authorization state from the authoritative control plane.

### MUST BACK UP

- No private key or secret is approved for raw migration by this gate.
- Before a later destructive step, export a **sanitised manifest** of device ID, certificate public fingerprints/serials, assigned camera/site, approved network profile identifiers, release receipt, effective config hash and required retention/audit references.
- Preserve any locally buffered customer captures that Headend has not acknowledged. The present read-only inspection did not prove that backlog is empty; this must be checked by the normal application-level acknowledgement mechanism before re-image.

### ARCHIVE AS EVIDENCE

- This gate report and the sanitised inventory hashes.
- Release receipt and source commit identifiers.
- Public certificate fingerprints/serials and key types only.
- The orphan camera-session capability remains recoverable from Git commit `6c5e3cac`; no raw device copy is needed.

### DO NOT MIGRATE

- Edge1's weak SSH policy, iperf3 service, desktop/CUPS/Snap/Samba remnants, legacy `/etc/timelapse/tls`, old CMDB Git/apt updater, backup files, caches, test artefacts and permissive historical sudoers fragments.
- Existing private keys or secrets as an expedient substitute for a governed re-issuance path.

## Required closure evidence

The next gate can pass only after:

1. The reconciled Golden Edge fix is merged to main and all Builder contract tests pass.
2. A clean image built from the exact accepted main SHA boots on equivalent Orange Pi hardware and demonstrates the full capability chain, including AP fallback, no-GPS NTP fallback, GPS time, watchdog recovery and reboot/power-loss recovery.
3. A dry-run or sacrificial-device rehearsal proves identity issuance, assignment/config restoration, technician access, break-glass behavior and old-identity revocation without copying secrets.
4. Edge1's unacknowledged capture/backlog count is proven zero or its payload is preserved through the governed retention path.
5. The final pre-destruction manifest is generated and reviewed against this document.

This decision does not authorize a re-image. Edge1 and Edge2 were unchanged.

EDGE1 RE-IMAGE GATE: BLOCKED
