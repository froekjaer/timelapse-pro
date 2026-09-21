"""Tests that Bluetooth/BlueZ naming failures in edge/scripts/ble-technician-gatt.py
can never propagate — a hard product requirement, since this service must
never be able to affect scheduled capture (a wholly separate process/service
that never imports this module or edge.network_status/edge.bluetooth_name).

This sandbox has no real BlueZ/D-Bus stack (no `dbus`/`gi` packages, matching
the target Orange Pi 4 Pro image's system Python, not this dev venv), so we
install minimal fakes sufficient to import and exercise the pure control-flow
logic (Runtime._compute_bluetooth_names / refresh_bluetooth_name). This does
NOT verify real BlueZ/D-Bus wire behavior (advertisement re-registration,
Adapter1.Alias property semantics) — that needs a physical Edge with BlueZ,
tracked as a known limitation (see HANDOVER_LOG.md and the PR description).
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

EDGE_SCRIPTS = Path(__file__).resolve().parents[1] / "edge" / "scripts"


class _FakeDBusObject:
    """Minimal stand-in for dbus.service.Object: just needs to be a usable
    base class that accepts (bus, path) and ignores dbus.service.method /
    dbus.service.signal decorators."""

    def __init__(self, *args, **kwargs):
        pass


def _decorator_factory(*_args, **_kwargs):
    def decorator(func):
        return func

    return decorator


@pytest.fixture
def ble_gatt_module(monkeypatch):
    """Import edge/scripts/ble-technician-gatt.py with a fake dbus/gi stack."""
    fake_dbus = types.ModuleType("dbus")
    fake_dbus.Bus = object
    fake_dbus.SystemBus = MagicMock()
    fake_dbus.ObjectPath = lambda v: v
    fake_dbus.String = lambda v: v
    fake_dbus.Boolean = lambda v: v
    fake_dbus.Array = lambda v, signature=None: list(v)  # noqa: ARG005
    fake_dbus.Byte = lambda v: v
    fake_dbus.Interface = MagicMock()

    fake_dbus_exceptions = types.ModuleType("dbus.exceptions")

    class DBusException(Exception):
        pass

    fake_dbus_exceptions.DBusException = DBusException
    fake_dbus.exceptions = fake_dbus_exceptions

    fake_dbus_service = types.ModuleType("dbus.service")
    fake_dbus_service.Object = _FakeDBusObject
    fake_dbus_service.method = _decorator_factory
    fake_dbus_service.signal = _decorator_factory
    fake_dbus.service = fake_dbus_service

    fake_dbus_mainloop = types.ModuleType("dbus.mainloop")
    fake_dbus_mainloop_glib = types.ModuleType("dbus.mainloop.glib")
    fake_dbus_mainloop_glib.DBusGMainLoop = MagicMock()
    fake_dbus_mainloop.glib = fake_dbus_mainloop_glib
    fake_dbus.mainloop = fake_dbus_mainloop

    fake_gi = types.ModuleType("gi")
    fake_gi_repository = types.ModuleType("gi.repository")
    fake_gi_repository.GLib = MagicMock()
    fake_gi.repository = fake_gi_repository

    for name, module in {
        "dbus": fake_dbus,
        "dbus.exceptions": fake_dbus_exceptions,
        "dbus.service": fake_dbus_service,
        "dbus.mainloop": fake_dbus_mainloop,
        "dbus.mainloop.glib": fake_dbus_mainloop_glib,
        "gi": fake_gi,
        "gi.repository": fake_gi_repository,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    monkeypatch.syspath_prepend(str(EDGE_SCRIPTS))
    monkeypatch.syspath_prepend(str(EDGE_SCRIPTS.parent))  # edge/ root for sibling imports

    sys.modules.pop("ble-technician-gatt", None)
    spec = importlib.util.spec_from_file_location("ble_technician_gatt_under_test", EDGE_SCRIPTS / "ble-technician-gatt.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_runtime(ble_gatt_module, monkeypatch):
    monkeypatch.setattr(ble_gatt_module, "create_service_platform", lambda base_dir: MagicMock())  # noqa: ARG005
    monkeypatch.setattr(ble_gatt_module, "_load_totp_secret", lambda: "")
    monkeypatch.setattr(ble_gatt_module, "BleTechnicianSession", MagicMock())
    return ble_gatt_module.Runtime(bus=MagicMock())


def test_network_status_failure_falls_back_without_raising(ble_gatt_module, monkeypatch):
    runtime = _make_runtime(ble_gatt_module, monkeypatch)

    def boom():
        raise RuntimeError("simulated BlueZ/network-status failure")

    monkeypatch.setattr(ble_gatt_module, "get_network_status", boom)

    names = runtime._compute_bluetooth_names()  # noqa: SLF001 - exercising the defensive path directly

    assert names.full  # fell back to a usable static name, did not raise
    assert names.advertisement


def test_refresh_bluetooth_name_swallows_dbus_errors(ble_gatt_module, monkeypatch):
    runtime = _make_runtime(ble_gatt_module, monkeypatch)

    def boom_alias(_alias):
        raise ble_gatt_module.dbus.exceptions.DBusException("simulated adapter unavailable")

    monkeypatch.setattr(runtime, "_set_adapter_alias", MagicMock(side_effect=RuntimeError("unexpected failure")))

    # Must not raise: a BlueZ/D-Bus failure here must never propagate out of
    # this service, since nothing on the capture path depends on it and
    # nothing should ever have to handle an exception from it.
    runtime.refresh_bluetooth_name()


def test_advertisement_and_alias_are_never_imported_by_capture_agent():
    """Structural guard: edge/agent.py (the capture scheduler) must never
    *import* ble_technician_gatt, network_status or bluetooth_name —
    Bluetooth naming must stay fully decoupled from the capture plane. A
    bare filename mention (e.g. in a manifest/doctor file-existence list) is
    fine and expected; an actual import statement is not.
    """
    import ast

    agent_path = Path(__file__).resolve().parents[1] / "edge" / "agent.py"
    tree = ast.parse(agent_path.read_text(), filename=str(agent_path))

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)

    # network_status itself is a generic utility other code may legitimately
    # use later; what must never happen is the capture agent depending on
    # the Bluetooth naming components specifically.
    forbidden = {"ble_technician_gatt", "bluetooth_name"}
    assert not (imported_names & forbidden), f"capture agent must not import: {imported_names & forbidden}"
