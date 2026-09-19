#!/usr/bin/env python3
"""BlueZ GATT peripheral for local technician access.

The service is deliberately a transport adapter. It exposes no shell and
delegates authenticated operation requests to BleTechnicianSession.

The Bluetooth device name (both the classic adapter Alias and the BLE
advertisement LocalName) is derived from current network status
(edge.network_status) via edge.bluetooth_name and kept in sync on a periodic
timer (see Runtime.refresh_bluetooth_name / BLUETOOTH_NAME_REFRESH_INTERVAL_SECONDS).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import glob
from pathlib import Path

# BlueZ D-Bus bindings belong to system Python, while ServiceOperations and
# cryptography are installed in the Edge venv. Keep both import surfaces explicit.
for _site in glob.glob("/opt/timelapse/venv/lib/python*/site-packages"):
    if _site not in sys.path:
        sys.path.insert(0, _site)
import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

EDGE_ROOT = Path(os.getenv("TIMELAPSE_EDGE_DIR", "/opt/timelapse/edge"))
if str(EDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(EDGE_ROOT))

from ble_technician_protocol import (  # noqa: E402
    AUTH_UUID,
    REQUEST_UUID,
    RESPONSE_UUID,
    SERVICE_UUID,
    STATUS_UUID,
)
from ble_technician_service import BleTechnicianSession  # noqa: E402
from bluetooth_name import compute_bluetooth_names  # noqa: E402
from network_status import get_network_status  # noqa: E402
from service_operations import create_service_platform  # noqa: E402
from totp_verifier import verify_totp  # noqa: E402

# How often the advertised/adapter Bluetooth name is recomputed from current
# network status. Independent of, and much slower than, anything on the
# capture path — a missed or failed tick only leaves the previous name in
# place (see Runtime.refresh_bluetooth_name).
BLUETOOTH_NAME_REFRESH_INTERVAL_SECONDS = 15


BLUEZ = "org.bluez"
GATT_MANAGER = "org.bluez.GattManager1"
LE_ADVERTISING_MANAGER = "org.bluez.LEAdvertisingManager1"
GATT_SERVICE = "org.bluez.GattService1"
GATT_CHARACTERISTIC = "org.bluez.GattCharacteristic1"
LE_ADVERTISEMENT = "org.bluez.LEAdvertisement1"
OBJECT_MANAGER = "org.freedesktop.DBus.ObjectManager"
PROPERTIES = "org.freedesktop.DBus.Properties"
AGENT_PATH = "/org/timelapse/ble/technician"
APPLICATION_PATH = AGENT_PATH + "/application"
SERVICE_PATH = APPLICATION_PATH + "/service"

log = logging.getLogger("ble-technician-gatt")


def _bytes(value: bytes) -> dbus.Array:
    return dbus.Array([dbus.Byte(byte) for byte in value], signature="y")


class Application(dbus.service.Object):
    def __init__(self, bus: dbus.Bus):
        super().__init__(bus, APPLICATION_PATH)
        self.service = TechnicianService(bus, SERVICE_PATH)

    @dbus.service.method(OBJECT_MANAGER, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        objects = {self.service.object_path: self.service.get_properties()}
        for characteristic in self.service.characteristics:
            objects[characteristic.object_path] = characteristic.get_properties()
        return objects


class TechnicianService(dbus.service.Object):
    def __init__(self, bus: dbus.Bus, path: str):
        super().__init__(bus, path)
        self.object_path = path
        self.characteristics = [
            AuthCharacteristic(bus, path + "/auth"),
            RequestCharacteristic(bus, path + "/request"),
            ResponseCharacteristic(bus, path + "/response"),
            StatusCharacteristic(bus, path + "/status"),
        ]
        self.response_characteristic = self.characteristics[2]
        self.status_characteristic = self.characteristics[3]

    def get_properties(self):
        return {
            GATT_SERVICE: {
                "UUID": dbus.String(SERVICE_UUID),
                "Primary": dbus.Boolean(True),
            }
        }


class Characteristic(dbus.service.Object):
    UUID = ""
    FLAGS: list[str] = []

    def __init__(self, bus: dbus.Bus, path: str):
        super().__init__(bus, path)
        self.object_path = path

    def get_properties(self):
        return {
            GATT_CHARACTERISTIC: {
                "Service": dbus.ObjectPath(SERVICE_PATH),
                "UUID": dbus.String(self.UUID),
                "Flags": dbus.Array(self.FLAGS, signature="s"),
            }
        }

    @dbus.service.method(PROPERTIES, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self.get_properties().get(interface, {})

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        raise dbus.exceptions.DBusException("org.bluez.Error.NotSupported")

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="aya{sv}")
    def WriteValue(self, value, options):
        raise dbus.exceptions.DBusException("org.bluez.Error.NotSupported")


class AuthCharacteristic(Characteristic):
    UUID = AUTH_UUID
    FLAGS = ["write", "write-without-response"]

    def WriteValue(self, value, options):
        service = _service()
        payload = bytes(value)
        log.info("BLE auth attempt")
        service.session_response(service.session.handle_auth(payload))


class RequestCharacteristic(Characteristic):
    UUID = REQUEST_UUID
    FLAGS = ["write", "write-without-response"]

    def WriteValue(self, value, options):
        service = _service()
        service.session_response(service.session.handle_request(bytes(value)))
        service.status_characteristic.emit_status()


class ResponseCharacteristic(Characteristic):
    UUID = RESPONSE_UUID
    FLAGS = ["read", "notify"]

    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.value = b"{}"
        self.notifying = False

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return _bytes(self.value)

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="a{sv}")
    def StartNotify(self, options):
        self.notifying = True

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="a{sv}")
    def StopNotify(self, options):
        self.notifying = False

    @dbus.service.signal(PROPERTIES, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    def publish(self, value: bytes):
        self.value = value
        if self.notifying:
            self.PropertiesChanged(GATT_CHARACTERISTIC, {"Value": _bytes(value)}, [])


class StatusCharacteristic(Characteristic):
    UUID = STATUS_UUID
    FLAGS = ["read", "notify"]

    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.notifying = False

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options):
        return _bytes(_status_payload())

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="a{sv}")
    def StartNotify(self, options):
        self.notifying = True

    @dbus.service.method(GATT_CHARACTERISTIC, in_signature="a{sv}")
    def StopNotify(self, options):
        self.notifying = False

    @dbus.service.signal(PROPERTIES, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    def emit_status(self):
        if self.notifying:
            self.PropertiesChanged(GATT_CHARACTERISTIC, {"Value": _bytes(_status_payload())}, [])


class Advertisement(dbus.service.Object):
    PATH = AGENT_PATH + "/advertisement"

    def __init__(self, bus):
        super().__init__(bus, self.PATH)
        # Placeholder until Runtime computes the real network-derived name
        # before the first RegisterAdvertisement call (see Runtime.__init__).
        self.local_name = os.uname().nodename[:26]

    def set_local_name(self, name: str) -> None:
        self.local_name = name

    @dbus.service.method(PROPERTIES, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != LE_ADVERTISEMENT:
            return {}
        return {
            "Type": dbus.String("peripheral"),
            "LocalName": dbus.String(self.local_name),
            "ServiceUUIDs": dbus.Array([SERVICE_UUID], signature="s"),
            "Includes": dbus.Array(["tx-power"], signature="s"),
        }

    @dbus.service.method(LE_ADVERTISEMENT)
    def Release(self):
        log.info("BLE advertisement released")


class Runtime:
    def __init__(self, bus):
        self.bus = bus
        self.adapter_path = dbus.ObjectPath("/org/bluez/hci0")
        self.application = Application(bus)
        self.advertisement = Advertisement(bus)
        self.platform = create_service_platform(base_dir=EDGE_ROOT)
        secret = _load_totp_secret()
        self.session = BleTechnicianSession(
            self.platform,
            totp_verifier=lambda code: _verify_totp(secret, code),
        )
        self._advertised_name: str | None = None
        # Compute the real network-derived name before the advertisement is
        # ever registered, so startup doesn't need an immediate unregister/
        # re-register churn (see refresh_bluetooth_name for the update path).
        self._apply_bluetooth_name(self._compute_bluetooth_names())

    def register(self):
        manager = dbus.Interface(self.bus.get_object(BLUEZ, self.adapter_path), GATT_MANAGER)
        manager.RegisterApplication(APPLICATION_PATH, {}, reply_handler=self._ok, error_handler=self._error)
        self._register_advertisement()
        self._set_adapter_alias(self._pending_full_alias)

    def _register_advertisement(self):
        advertising = dbus.Interface(self.bus.get_object(BLUEZ, self.adapter_path), LE_ADVERTISING_MANAGER)
        advertising.RegisterAdvertisement(Advertisement.PATH, {}, reply_handler=self._ok, error_handler=self._error)

    def _unregister_advertisement(self):
        try:
            advertising = dbus.Interface(self.bus.get_object(BLUEZ, self.adapter_path), LE_ADVERTISING_MANAGER)
            advertising.UnregisterAdvertisement(Advertisement.PATH)
        except dbus.exceptions.DBusException as exc:
            # BlueZ only picks up a new LocalName on (re-)registration, so an
            # update always unregisters first. If nothing was registered yet
            # (or BlueZ already dropped it), that's fine — proceed to
            # register the new one regardless.
            log.debug("BLE advertisement unregister before refresh: %s", exc)

    def _compute_bluetooth_names(self):
        """Never raises: a network-status/name-computation failure must never
        prevent BLE GATT/advertisement registration or crash this process,
        let alone anything on the capture path (product requirement: BT/
        network-discovery failure must never stop scheduled capture, and
        this module has no coupling to capture at all)."""
        try:
            hostname = os.uname().nodename
            status = get_network_status()
            return compute_bluetooth_names(hostname, status)
        except Exception:
            log.exception("Network-status lookup failed; falling back to static hostname")
            fallback = os.uname().nodename[:26]

            class _Fallback:
                full = fallback
                advertisement = fallback

            return _Fallback()

    def _apply_bluetooth_name(self, names) -> None:
        self.advertisement.set_local_name(names.advertisement)
        self._pending_full_alias = names.full
        self._advertised_name = names.advertisement

    def _set_adapter_alias(self, alias: str) -> None:
        try:
            props = dbus.Interface(self.bus.get_object(BLUEZ, self.adapter_path), PROPERTIES)
            props.Set("org.bluez.Adapter1", "Alias", dbus.String(alias))
        except dbus.exceptions.DBusException:
            log.exception("Failed to set adapter Alias (classic BT-PAN/inquiry name); advertisement name unaffected")

    def refresh_bluetooth_name(self) -> None:
        """Recompute the network-derived Bluetooth name and apply it if it
        changed. Called periodically from the GLib main loop (see main()).
        Defensive by design: any failure here is logged and swallowed so
        Bluetooth naming can never affect anything else on the Edge.
        """
        names = self._compute_bluetooth_names()
        try:
            self._set_adapter_alias(names.full)  # idempotent D-Bus property set; cheap even if unchanged
            if names.advertisement != self._advertised_name:
                self.advertisement.set_local_name(names.advertisement)
                self._unregister_advertisement()
                self._register_advertisement()
                self._advertised_name = names.advertisement
                log.info("Bluetooth name updated: full=%s advertisement=%s", names.full, names.advertisement)
        except Exception:
            log.exception("Failed to apply updated Bluetooth name; will retry on next refresh")

    def _ok(self):
        log.info("BLE GATT component registered")

    def _error(self, error):
        log.error("BLE registration failed: %s", error)
        raise SystemExit(1)

    def response(self, value: bytes):
        self.application.response_characteristic.publish(value)

    def session_response(self, value: bytes):
        """Publish a response without exposing the session object to GATT code."""
        self.response(value)

    def shutdown(self):
        self.session.invalidate("ble_service_shutdown")


_RUNTIME: Runtime | None = None


def _service():
    if _RUNTIME is None:
        raise RuntimeError("BLE runtime not initialized")
    return _RUNTIME


def _status_payload() -> bytes:
    return json.dumps(_service().session.status(), separators=(",", ":")).encode("utf-8")


def _load_totp_secret() -> str:
    try:
        import yaml

        data = yaml.safe_load(Path("/etc/timelapse/bt-config.yaml").read_text()) or {}
        return str((data.get("totp") or {}).get("secret") or "")
    except (OSError, ValueError, TypeError):
        return ""


def _verify_totp(secret: str, code: str) -> bool:
    return verify_totp(secret, code, window=3)


def _refresh_bluetooth_name_tick() -> bool:
    if _RUNTIME is not None:
        _RUNTIME.refresh_bluetooth_name()
    return True  # keep the GLib timeout repeating


def main():
    global _RUNTIME
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [ble-gatt] %(message)s")
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    _RUNTIME = Runtime(bus)
    _RUNTIME.register()
    GLib.timeout_add_seconds(BLUETOOTH_NAME_REFRESH_INTERVAL_SECONDS, _refresh_bluetooth_name_tick)
    try:
        GLib.MainLoop().run()
    finally:
        _RUNTIME.shutdown()


if __name__ == "__main__":
    main()
