# WP-3 Unified Technician Platform

Dato: 2026-08-15

## Contract

Der findes én lokal service backend på Edge: `edge/service_platform.py`.

Klienter:

- Local Technician UI `/mgmt/technician`
- `tlservice` / `edge/tools/bootstrap_cli.py`
- LAB Mode i `edge/agent.py`
- fremtidig AI Service Assistant

skal bruge samme Service Operations, ServiceSession, capabilities, leases, status og audit.

## Canonical objects

- `ServiceSession`: principal, EdgeServiceGrant reference, capabilities, created_at, last_activity, idle timeout, absolute timeout.
- `HardwareLease`: session-owned leases for hardware/resource ownership.
- `ServicePlatform`: operation registry, capability enforcement, lease manager, shared status and audit writer.

## Lease types

- `CameraPowerLease`
- `LiveViewLease`
- `TemporaryConfigLease`
- `DiagnosticLease`
- `ModemMaintenanceLease`

Ingen serviceoperation må aktivere hardware uden en lease.

## Registered operations

WP-3 registry contains the required operations:

- `camera.status`
- `camera.detect`
- `camera.ptp.diagnostics`
- `camera.power.acquire`
- `camera.power.release`
- `camera.power.cycle`
- `camera.capture.test`
- `camera.live.start`
- `camera.live.stop`
- `camera.config.read`
- `camera.config.diff`
- `camera.config.set_temporary`
- `camera.usb.rediscover`
- `camera.driver.reconnect`
- `camera.hardware.inventory`
- `camera.focus.manual`
- `camera.focus.auto`
- `camera.exposure.test`
- `image.quality.diagnostics`
- `camera.reset`
- `camera.diagnostics`
- `modem.status`
- `modem.signal`
- `modem.registration`
- `modem.reconnect_history`
- `modem.power.cycle`
- `network.status`
- `network.diagnostics`
- `storage.status`
- `system.status`
- `system.logs`
- `timelapse.service.status`
- `timelapse.service.restart`
- `certificate.trust.status`
- `software.update.status`
- `diagnostic.bundle`
- `system.reboot`
- `commissioning.run`
- `commissioning.validate`

## Capability Matrix

| Operation group | Required capability | Technician | Senior Technician | Engineer | Break Glass | LAB |
|---|---:|---:|---:|---:|---:|---:|
| Camera status, detect, inventory, USB/PTP diagnostics | `camera.read`, `camera.hardware`, `camera.diagnostics` | yes | yes | yes | yes | yes |
| Camera power acquire/release/cycle | `camera.power` | yes | yes | yes | yes | yes |
| Live View | `camera.live` | yes | yes | yes | yes | yes |
| Test capture | `camera.capture.test` | yes | yes | yes | yes | yes |
| Config read/diff | `camera.config.read` | yes | yes | yes | yes | yes |
| Temporary config set | `camera.config.temporary` | yes | yes | yes | yes | yes |
| Focus/exposure test | `camera.focus`, `camera.exposure` | yes | yes | yes | yes | yes |
| Camera reset | `camera.reset` | no | yes | yes | yes | yes |
| Modem status/signal/registration/history | `modem.read` | yes | yes | yes | yes | yes |
| Modem power-cycle | `modem.power` | no | yes | yes | yes | yes |
| Network/storage/system/trust/software read | `network.read`, `storage.read`, `system.read`, `trust.read`, `software.read` | yes | yes | yes | yes | yes |
| TimeLapse controlled restart | `system.service.restart` | no | yes | yes | yes | yes |
| Controlled reboot | `system.reboot` | no | no | yes | yes | no |
| Commissioning run | `commissioning.run` | no | yes | yes | yes | yes |
| Commissioning validate | `commissioning.validate` | yes | yes | yes | yes | yes |

## Shared status

`ServicePlatform.status()` is the canonical status for UI and CLI:

- logged in
- camera relay ON/OFF
- camera detected
- PTP connected
- Live View ON/OFF
- Config dirty count
- Session expiry
- Grant expiry
- Last activity
- Active leases

## Invalidation

`ServicePlatform.invalidate()` is called or reached fail-closed when a grant is expired/revoked, logout/shutdown/cleanup occurs, or session timeouts fire.

Invalidation releases all leases, stops live-view state, clears temporary state, marks session inactive and writes audit. Hardware shutdown is owned by the lease-holding operation manager; status is fail-closed after invalidation.

## Client routing

- `edge/service_operations.py` owns concrete Service Operations handlers and adapts existing camera, modem, network, storage, system, trust/update and commissioning helpers.
- CLI maintenance camera operations and generic `--service-operation` calls route through `ServicePlatform.call(operation_name, ...)`.
- UI Live View start/stop and technician action buttons call the same Service Operations backend and render the shared status.
- LAB Mode acquires `camera.power.acquire` before preparing the camera and invalidates the service session when LAB is disabled.

## CommissioningReport v1

`commissioning.run` emits schema `timelapse.edge.commissioning_report.v1` with result:

- `PASS`
- `PASS WITH DEVIATIONS`
- `FAIL`

Required sections:

- identity
- hardware
- camera
- test capture
- image quality
- modem/network
- GPS/time
- storage
- certificates
- Headend connectivity
- software version
- technician
- deviations

## Technician Experience Completion Gate

Covered operations:

- camera status, power acquire/release/cycle, detect, reconnect, USB/PTP diagnostics, hardware inventory, live view, test capture, config read/temporary set/diff, autofocus/manual focus/exposure test, image quality diagnostics
- modem status, signal, registration, reconnect history and power-cycle
- network diagnostics, storage/backlog, system health, TimeLapse service status/restart, trust/certificate status, software/update status, diagnostic bundle and controlled reboot
- CommissioningReport v1 and validation

Missing or deferred operations:

- physical PASS for all camera fields depends on connected hardware support for model/serial/firmware/battery/shutter count
- CSR/PKI redesign, generator redesign and browser terminal remain out of scope
- LAB-only command paths should continue to be migrated case-by-case when new LAB commands are added
- legacy bootstrap CLI helper functions for non-technician bootstrap/network compatibility still exist in `edge/tools/bootstrap_cli.py`; active technician actions, generic `--service-operation` and `/mgmt/technician` route through `edge/service_operations.py`
- low-level HAL, gphoto2, system service and modem/network adapter calls remain inside the Service Operations backend, where hardware/system access is allowed

UI/CLI parity:

- Backend parity is established through `edge/service_operations.py` and `ServicePlatform.call`.
- CLI exposes generic `--service-operation` and `--commissioning-report`.
- `/mgmt/technician` uses the same backend through the CLI bridge and direct live-view backend injection.

Safety cleanup:

- Camera operations that take `CameraPowerLease` acquire physical camera power through the lease acquire hook and release it through cleanup handlers when `release_after` or invalidation runs.
- Central grant revoke/expiry still propagates through technician auth to `ServicePlatform.invalidate()` and physical cleanup.

## Boundary

WP-3 establishes the platform and routes current service clients through it. Further user-facing tools should add operations to the registry instead of adding direct hardware logic to UI, CLI, LAB or AI assistant code.
