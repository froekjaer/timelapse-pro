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
- `modem.power.on` (2026-10-03)
- `modem.power.test` — sluk i 10 s, tændes automatisk fra en løsrevet proces startet FØR sluk (2026-10-03)
- `relay.status` — pins og faktisk GPIO-tilstand, kun læsning (2026-10-03)
- `camera.relay.pin_test` — midlertidigt kamera-testpin; permanent pin sættes i UI/DB (2026-10-03)
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
| Modem power on / 10 s test | `modem.power` | no | yes | yes | yes | yes |
| Relay status | `camera.read` | yes | yes | yes | yes | yes |
| Camera relay test pin | `camera.reset` | no | yes | yes | yes | yes |
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

Aggregation rules:

- nested section failures propagate to the top-level result, including `modem_network.modem` and `modem_network.network`
- failed checks produce `FAIL`
- deviations without failed checks produce `PASS WITH DEVIATIONS`
- upload backlog alone is a deviation, not a fail
- certificate/trust status parses the existing management certificate and trust anchor read-only, reports subject, SAN, SHA-256 fingerprint, validity/expiry and verifies the chain where the existing Edge-local PKI material is present

## Technician Experience Completion Gate

Covered operations:

- camera status, power acquire/release/cycle, detect, reconnect, USB/PTP diagnostics, hardware inventory, live view, test capture, config read/temporary set/diff, autofocus/manual focus/exposure test, image quality diagnostics
- modem status, signal, registration, reconnect history and power-cycle
- network diagnostics, storage/backlog, system health, TimeLapse service status/restart, trust/certificate status, software/update status, diagnostic bundle and controlled reboot
- CommissioningReport v1 and validation, including nested modem/network failure propagation and certificate missing/invalid/expired/valid coverage

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

## Modemrelæ-regel (Peter, 2026-10-03)

Modemrelæet må ALDRIG miste strøm uden en eksplicit kommando: ikke ved agent-start (`RelayController` initialiserer modem-pinnet direkte i ON og rører det ikke, hvis det allerede er drevet), ikke ved agent-stop (`cleanup(modem=False)`), ikke som bivirkning af en serviceoperation (`cleanup_modem` er no-op). `RelayController.cleanup()` har `modem=False` som standard. Eksplicitte veje: `modem.power.cycle`, `modem.power.test` og LAB-relækommandoen. Bevidst undtagelse (Peter, 2026-10-03: "Behold som i dag"): `ConnectivityMonitor`'s automatiske power-cycle efter `modem_cycle_after_failures` fejl (højst hvert `modem_min_cycle_interval_s`), konfigureret i UI (System Administration), tæller som tilladt genoprettelse.

## Lokal CLI-autoritet (Peter, 2026-10-04)

`ServicePlatform.start_local_cli_session(user)` er en eksplicit autoritetsadapter (som `start_lab_session`) for tekniker-CLI'en, når den kører som **root via sudo**: brugeren er allerede autentificeret over for OS'et (SSH-nøgle/adgangskode + sudo) og kunne som root styre hardwaren direkte, så et ekstra TOTP-login i web-UI'en gav ingen beskyttelse — kun en forhindring (fx via tunnelen, hvor tekniker-UI'en ikke nås). Principal `cli:<SUDO_USER>`, rolle `local_cli`, `SENIOR_TECHNICIAN_CAPABILITIES` (kamera-strøm, modem-test, testpin; ingen reboot), grant-id `local-cli-…`, samme registry/leases/audit. En eksisterende session fra tekniker-UI'en genbruges og afsluttes ikke; en CLI-startet session invalideres når menuen forlades. Uden sudo: besked om at køre med sudo. Bemærk: audit-filen ligger i `/run/timelapse` og overlever ikke genstart (eksisterende forhold).

## Kamera-lease uden at stoppe agenten (Peter, 2026-10-04)

"At tænde et relæ må ikke koste netværksforbindelsen." Tidligere stoppede `CameraPowerLease` hele `timelapse-edge` — og agenten ejer reverse-tunnel, sync og heartbeat. Nu: agenten tager `CameraMaintenanceLease` (flock på `/run/timelapse/camera-maintenance.lock`, timeout 0) for hver planlagt billedcyklus; er låsen holdt af en tekniker, markeres slottet `skipped`/`technician_maintenance` uden alarm og uden at røre relæet. Agenten annoncerer `{"camera_maintenance_lock": true}` i `/run/timelapse/agent-features.json`; `ServiceOperations.acquire_camera_power` tager da låsen (venter op til 90 s på et igangværende billede) og tænder relæet uden at stoppe agenten, og frigivelsen unexport'er ikke pinnet (agentens controller bruger det). Dør teknikerprocessen, frigiver kernen låsen. Ældre agenter uden annoncering stoppes/genstartes som før.
