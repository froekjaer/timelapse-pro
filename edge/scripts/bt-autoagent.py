#!/usr/bin/env python3
"""
TimeLapse Pro — BT pairing agent
Auto-accepterer User Confirmation Requests (Just Works / Numeric Comparison)
Kræver: python3-dbus, python3-gi
"""
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import logging
import sys

logging.basicConfig(level=logging.INFO, format='[bt-autoagent] %(message)s')
log = logging.getLogger(__name__)

AGENT_INTERFACE = "org.bluez.Agent1"
AGENT_PATH = "/org/timelapse/BTAgent"


class AutoAgent(dbus.service.Object):
    def __init__(self, bus, path):
        dbus.service.Object.__init__(self, bus, path)

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Release(self):
        log.info("Agent released")

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        log.info(f"AuthorizeService: {device} uuid={uuid} → ACCEPT")
        return  # Auto-accept alle services (inkl. NAP)

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        log.info(f"RequestPinCode: {device} → '0000'")
        return "0000"

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        log.info(f"RequestPasskey: {device} → 0")
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_INTERFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        log.info(f"DisplayPasskey: {device} passkey={passkey}")

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        log.info(f"DisplayPinCode: {device} pin={pincode}")

    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        log.info(f"RequestConfirmation: {device} passkey={passkey:06d} → CONFIRM")
        return  # Auto-accepter

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        log.info(f"RequestAuthorization: {device} → ACCEPT")
        return  # Auto-accepter

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Cancel(self):
        log.info("Cancel")


NAP_BRIDGE = "br-bt"


def register_nap(bus):
    """Registrer NAP server med bluetoothd — holder D-Bus-forbindelsen åben."""
    try:
        net = dbus.Interface(
            bus.get_object("org.bluez", "/org/bluez/hci0"),
            "org.bluez.NetworkServer1"
        )
        net.Register("nap", NAP_BRIDGE)
        log.info(f"NAP registreret på bridge {NAP_BRIDGE}")
    except dbus.exceptions.DBusException as e:
        if "Already" in str(e):
            log.info("NAP allerede registreret")
        else:
            log.warning(f"NAP registrering fejlede: {e}")


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    agent = AutoAgent(bus, AGENT_PATH)

    mgr = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"),
        "org.bluez.AgentManager1"
    )
    mgr.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
    mgr.RequestDefaultAgent(AGENT_PATH)
    log.info("BT auto-agent registreret (NoInputNoOutput, auto-confirm)")

    register_nap(bus)

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            net = dbus.Interface(
                bus.get_object("org.bluez", "/org/bluez/hci0"),
                "org.bluez.NetworkServer1"
            )
            net.Unregister("nap")
        except Exception:
            pass
        mgr.UnregisterAgent(AGENT_PATH)
        log.info("Agent + NAP afmeldt")


if __name__ == "__main__":
    main()
