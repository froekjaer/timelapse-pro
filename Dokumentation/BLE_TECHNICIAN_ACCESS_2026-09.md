# BLE Technician Access — implementation baseline

## Purpose

Provide a second local recovery/configuration path for an Edge mounted in a
mast. WiFi AP remains the browser path. BLE is a transport for the same local
technician session and Service Operations; it is not a second hardware API.

## Verified current state

- The live Edge advertises Classic Bluetooth NAP/PAN and can establish an ACL
  Bluetooth connection with an iPhone.
- The iPhone did not request the Edge's NAP service, so no `bnep` interface or
  local IP path was created.
- The repository has no BLE GATT service or iOS client.
- iPhone accessory configuration uses CoreBluetooth/GATT from an iOS app; an
  iOS browser cannot be treated as a GATT client for the existing HTTPS UI.

## Target

The Edge will expose one custom BLE GATT service with bounded JSON messages:

| Characteristic | Direction | Purpose |
|---|---|---|
| `AUTH_UUID` | iPhone -> Edge | six-digit TOTP only |
| `REQUEST_UUID` | iPhone -> Edge | Service Operation request |
| `RESPONSE_UUID` | Edge -> iPhone | request result/error notification |
| `STATUS_UUID` | Edge -> iPhone | read-only session/device status |

The protocol constants and validation live in `edge/ble_technician_protocol.py`.
The adapter must create an explicit offline-recovery ServiceSession after a
valid local TOTP and dispatch requests through `ServicePlatform.call()`. It
must never call GPIO, gphoto, ModemManager or systemctl directly.

## Security rules

- TOTP is the current local access control. No shared/default secret is allowed.
- BLE messages are size- and type-bounded; malformed input fails closed.
- No private keys, credentials, camera images or arbitrary filesystem paths are
  returned over BLE.
- The BLE adapter has no shell or arbitrary-command operation.
- Session expiry/logout invalidates the shared ServiceSession and invokes the
  normal lease cleanup handlers.
- Every operation uses the existing capability and audit model.
- Pairing/trust state is not treated as authorization and is not changed by the
  adapter.

## Client boundary

The iPhone UI must be a native CoreBluetooth client (optionally distributed via
TestFlight). It can present the same operation/status vocabulary as the web UI,
but must call the BLE service rather than duplicate hardware behavior. Building
and signing that client requires an Xcode/iOS SDK environment; the current
development host has Swift but no Xcode installation.

## Current implementation

- `edge/ble_technician_protocol.py` — shared bounded message contract.
- `tests/test_ble_technician_protocol.py` — malformed, oversized, unsupported
  auth, and invalid parameter tests.

The GATT D-Bus adapter, iOS client, image installation and live Edge rollout
remain separate gates. No live Edge was changed by this implementation.
