#!/usr/bin/env python3
"""BlueZ GATT peripheral for local technician access.

The service is deliberately a transport adapter. It exposes no shell and
delegates authenticated operation requests to BleTechnicianSession.
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
from service_operations import create_service_platform  # noqa: E402
from totp_verifier import verify_totp  # noqa: E402


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

    @dbus.service.method(PROPERTIES, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != LE_ADVERTISEMENT:
            return {}
        return {
            "Type": dbus.String("peripheral"),
            "LocalName": dbus.String(os.uname().nodename[:26]),
            "ServiceUUIDs": dbus.Array([SERVICE_UUID], signature="s"),
            "Includes": dbus.Array(["tx-power"], signature="s"),
        }

    @dbus.service.method(LE_ADVERTISEMENT)
    def Release(self):
        log.info("BLE advertisement released")


class Runtime:
    def __init__(self, bus):
        self.bus = bus
        self.application = Application(bus)
        self.advertisement = Advertisement(bus)
        self.platform = create_service_platform(base_dir=EDGE_ROOT)
        secret = _load_totp_secret()
        self.session = BleTechnicianSession(
            self.platform,
            totp_verifier=lambda code: _verify_totp(secret, code),
        )

    def register(self):
        adapter = dbus.ObjectPath("/org/bluez/hci0")
        manager = dbus.Interface(self.bus.get_object(BLUEZ, adapter), GATT_MANAGER)
        manager.RegisterApplication(APPLICATION_PATH, {}, reply_handler=self._ok, error_handler=self._error)
        advertising = dbus.Interface(self.bus.get_object(BLUEZ, adapter), LE_ADVERTISING_MANAGER)
        advertising.RegisterAdvertisement(Advertisement.PATH, {}, reply_handler=self._ok, error_handler=self._error)

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


def main():
    global _RUNTIME
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [ble-gatt] %(message)s")
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    _RUNTIME = Runtime(bus)
    _RUNTIME.register()
    try:
        GLib.MainLoop().run()
    finally:
        _RUNTIME.shutdown()


if __name__ == "__main__":
    main()
