"""Tests for the target-resolution and DB-orchestration half of
headend/services/cmdb_baseline_drift.py. See test_cmdb_baseline_drift.py for
the pure comparison-function tests.
"""
import json

from services.cmdb_baseline_drift import reconcile_device_baseline, resolve_target_id


# ── resolve_target_id ────────────────────────────────────────────────────────

def _fake_loader(targets: dict):
    def load(target_id):
        return targets[target_id]
    return load


def test_resolve_target_id_matches_on_substring():
    targets = {
        "orangepi4pro": {"device_tree_model_patterns": ["orangepi 4 pro", "orange pi 4 pro", "rk3399"]},
        "rpi4": {"device_tree_model_patterns": ["raspberry pi 4"]},
    }
    resolved = resolve_target_id(
        "Orange Pi 4 Pro", "RK3399", list(targets), _fake_loader(targets)
    )
    assert resolved == "orangepi4pro"


def test_resolve_target_id_returns_none_when_nothing_matches():
    targets = {"rpi4": {"device_tree_model_patterns": ["raspberry pi 4"]}}
    resolved = resolve_target_id(
        "Unknown Board", "UnknownSoC", list(targets), _fake_loader(targets)
    )
    assert resolved is None


def test_resolve_target_id_handles_missing_fields():
    targets = {"rpi4": {"device_tree_model_patterns": ["raspberry pi 4"]}}
    assert resolve_target_id(None, None, list(targets), _fake_loader(targets)) is None


# ── reconcile_device_baseline ────────────────────────────────────────────────

class _FakeInventory:
    def __init__(self, device_id, hardware_model, soc_model, os_packages, software_inventory):
        self.device_id = device_id
        self.hardware_model = hardware_model
        self.soc_model = soc_model
        self.os_packages = json.dumps(os_packages)
        self.software_inventory = json.dumps(software_inventory)


class _FakeGrcItem:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeGrcQuery:
    def __init__(self, store, filters=None):
        self._store = store
        self._filters = filters or {}

    def filter_by(self, **kwargs):
        return _FakeGrcQuery(self._store, {**self._filters, **kwargs})

    def _matches(self, item):
        return all(getattr(item, k, None) == v for k, v in self._filters.items())

    def first(self):
        return next((item for item in self._store if self._matches(item)), None)

    def all(self):
        return [item for item in self._store if self._matches(item)]


class _FakeDb:
    def __init__(self, inventory):
        self._inventory = inventory
        self.grc_store: list = []
        self.committed = False

    def query(self, model):
        name = getattr(model, "__name__", str(model))
        if name == "DeviceInventory":
            return _InventoryQuery(self._inventory)
        return _FakeGrcQuery(self.grc_store)

    def add(self, obj):
        self.grc_store.append(obj)

    def commit(self):
        self.committed = True


class _InventoryQuery:
    def __init__(self, inventory):
        self._inventory = inventory

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return self._inventory


def _patch_target(monkeypatch, target_id, target):
    import services.cmdb_baseline_drift as mod
    monkeypatch.setattr(mod, "available_target_ids", lambda: [target_id])
    monkeypatch.setattr(mod, "load_target_yaml", lambda tid: target)


def _install_fake_database_module(monkeypatch):
    """reconcile_device_baseline does `from database import DeviceInventory, GrcItem`
    inside the function — patch the real `database` module's GrcItem so the
    lazy import picks up our fake, matching the way this codebase already
    lazy-imports models inside service functions.
    """
    import sys
    import types
    fake_db_module = types.ModuleType("database")
    fake_db_module.DeviceInventory = type("DeviceInventory", (), {})
    fake_db_module.GrcItem = _FakeGrcItem
    monkeypatch.setitem(sys.modules, "database", fake_db_module)


def test_reconcile_device_baseline_upserts_findings_for_real_drift(monkeypatch):
    _install_fake_database_module(monkeypatch)
    target = {
        "extra_packages": ["gpsd"],
        "expected_enabled_services": ["timelapse-edge.service"],
        "expected_local_users": ["orangepi"],
        "device_tree_model_patterns": ["orangepi 4 pro", "orange pi 4 pro"],
    }
    _patch_target(monkeypatch, "orangepi4pro", target)

    inv = _FakeInventory(
        "TL-TEST", "Orange Pi 4 Pro", "RK3399",
        os_packages={},
        software_inventory={"_enabled_services": [], "_local_users": []},
    )
    db = _FakeDb(inv)

    result = reconcile_device_baseline(db, "TL-TEST", "claude-2026-08-16")

    assert result["ok"] is True
    assert result["target_id"] == "orangepi4pro"
    assert result["findings_open"] == 3  # packages-missing, services-missing, accounts-missing
    assert db.committed is True
    assert len(db.grc_store) == 3


def test_reconcile_device_baseline_reports_no_matching_target():
    inv = _FakeInventory("TL-TEST", "Mystery Board", "MysterySoC", {}, {})
    db = _FakeDb(inv)

    result = reconcile_device_baseline(db, "TL-TEST", "claude-2026-08-16")

    assert result == {"ok": False, "error": "no_matching_hardware_target", "device_id": "TL-TEST"}


def test_reconcile_device_baseline_reports_no_inventory():
    db = _FakeDb(None)

    result = reconcile_device_baseline(db, "TL-GHOST", "claude-2026-08-16")

    assert result == {"ok": False, "error": "no_inventory", "device_id": "TL-GHOST"}
