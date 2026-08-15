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
- `camera.reset`
- `camera.diagnostics`
- `modem.status`
- `modem.signal`
- `modem.power.cycle`
- `network.status`
- `storage.status`
- `system.status`
- `system.logs`
- `system.reboot`
- `commissioning.run`
- `commissioning.validate`

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

- CLI maintenance camera operations call `ServicePlatform.call(operation_name, ...)`.
- UI Live View start/stop calls `camera.live.start` / `camera.live.stop` and renders the shared status.
- LAB Mode acquires `camera.power.acquire` before preparing the camera and invalidates the service session when LAB is disabled.

## Boundary

WP-3 establishes the platform and routes current service clients through it. Further user-facing tools should add operations to the registry instead of adding direct hardware logic to UI, CLI, LAB or AI assistant code.
