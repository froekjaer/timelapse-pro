"""Relays (Peter, 2026-10-03).

- The modem relay must NEVER lose power without an explicit command — not at
  agent start, not at agent stop, not as a side effect of a service operation.
- An explicit modem test switches it off for 10 s and back on automatically;
  the switch-on is scheduled in a detached process BEFORE switching off.
- HW-383A is active-low: "1" on the GPIO = relay off, "0" = relay on.
- The technician CLI relay menu goes through Service Operations (WP-3), never
  touches GPIO itself, and releases the relays when left (also on Ctrl+C).
"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))

from camera import relay as relay_mod  # noqa: E402
import service_operations as ops_mod  # noqa: E402
from service_platform import ServicePlatform, Principal, EdgeServiceGrantRef, TECHNICIAN_CAPABILITIES  # noqa: E402

_spec = importlib.util.spec_from_file_location("bootstrap_cli_relay_test", ROOT / "edge" / "tools" / "bootstrap_cli.py")
cli = importlib.util.module_from_spec(_spec)
sys.modules["bootstrap_cli_relay_test"] = cli
_spec.loader.exec_module(cli)

CAM, MODEM = 356, 361


def _gpio(root: Path, pin: int, direction: str = "in", value: str = "1") -> Path:
    d = root / f"gpio{pin}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "direction").write_text(direction)
    (d / "value").write_text(value)
    return d


@pytest.fixture
def sysfs(tmp_path, monkeypatch):
    """Fake sysfs that applies 'high'/'low' direction writes like the kernel."""
    monkeypatch.setattr(relay_mod, "GPIO_ROOT", tmp_path)
    monkeypatch.setattr(relay_mod, "PLATFORM", "rk3588")
    writes = []
    real = Path.write_text

    def write_text(path, data, *a, **kw):
        writes.append((path.parent.name, path.name, data))
        if path.name == "direction" and data in {"high", "low"}:
            real(path.parent / "value", "1" if data == "high" else "0")
            data = "out"
        return real(path, data, *a, **kw)

    monkeypatch.setattr(Path, "write_text", write_text)
    return SimpleNamespace(root=tmp_path, writes=writes)


def test_active_low_convention():
    assert relay_mod._RELAY_OFF == "1" and relay_mod._RELAY_ON == "0"


def test_agent_start_never_pulses_modem_off_or_camera_on(sysfs):
    _gpio(sysfs.root, CAM)
    _gpio(sysfs.root, MODEM)
    sysfs.writes.clear()
    relay_mod.RelayController({"camera": {"relay_gpio_pin": CAM}, "modem": {"modem_relay_gpio_pin": MODEM}})
    assert ("gpio361", "direction", "low") in sysfs.writes
    assert not [w for w in sysfs.writes if w[0] == "gpio361" and w[2] in {"1", "high"}]
    assert ("gpio356", "direction", "high") in sysfs.writes
    assert ("gpio356", "value", "0") not in sysfs.writes
    assert relay_mod.read_relay_state(MODEM) == "ON" and relay_mod.read_relay_state(CAM) == "OFF"


def test_agent_restart_leaves_running_modem_untouched(sysfs):
    _gpio(sysfs.root, CAM)
    _gpio(sysfs.root, MODEM, "out", "0")
    sysfs.writes.clear()
    relay_mod.RelayController({"camera": {"relay_gpio_pin": CAM}, "modem": {"modem_relay_gpio_pin": MODEM}})
    assert not [w for w in sysfs.writes if w[0] == "gpio361" and w[1] == "direction"]
    assert relay_mod.read_relay_state(MODEM) == "ON"


def test_cleanup_default_keeps_modem_on():
    calls = []
    fake = SimpleNamespace(
        camera=SimpleNamespace(force_off=lambda: calls.append("cam_off"), _pin=CAM),
        modem=SimpleNamespace(force_off=lambda: calls.append("modem_off"), _pin=MODEM),
        _backend=SimpleNamespace(cleanup=lambda pins: calls.append(("cleanup", tuple(pins)))),
    )
    relay_mod.RelayController.cleanup(fake)
    assert "modem_off" not in calls and ("cleanup", (CAM,)) in calls


def test_agent_shutdown_and_service_ops_keep_modem_on():
    agent_src = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
    assert "self._relay.cleanup(camera=self._camera_uses_relay(), modem=False)" in agent_src
    ops = ops_mod.ServiceOperations()
    assert ops.cleanup_modem(None, None, "done") is None


def test_modem_relay_has_power_on_for_lab_toggle():
    calls = []
    modem = relay_mod.ModemRelay(SimpleNamespace(set=lambda pin, on: calls.append((pin, on))), {}, MODEM)
    modem.power_on()
    assert calls[-1] == (MODEM, True) and modem.is_on


def _ops(monkeypatch):
    ops = ops_mod.ServiceOperations()
    monkeypatch.setattr(ops, "_relay_pins", lambda: {"platform": "rk3588", "camera": CAM, "modem": MODEM})
    monkeypatch.setattr(ops, "_service_state", lambda _s: {"active": "inactive"})
    return ops


def test_modem_test_schedules_restore_before_switching_off(sysfs, monkeypatch):
    _gpio(sysfs.root, MODEM, "out", "0")
    order = []
    monkeypatch.setattr(relay_mod.subprocess if hasattr(relay_mod, "subprocess") else __import__("subprocess"),
                        "Popen", lambda cmd, **kw: order.append(("restore", kw.get("start_new_session"), cmd[-1])))
    monkeypatch.setattr(relay_mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(ops_mod.time, "sleep", lambda s: order.append(("sleep", s)))
    real_set = relay_mod.set_relay_pin
    monkeypatch.setattr(relay_mod, "set_relay_pin", lambda pin, on: (order.append(("set", pin, on)), real_set(pin, on)))
    result = _ops(monkeypatch).modem_power_test(None, None, {"off_seconds": 10})
    assert order[0][0] == "restore" and order[0][1] is True
    assert "gpio361" in order[0][2] and "time.sleep(10.0)" in order[0][2] and "'0'" in order[0][2]
    assert order[1] == ("set", MODEM, False)
    assert result["ok"] is True and relay_mod.read_relay_state(MODEM) == "ON"


def test_status_pin_test_and_cleanup(sysfs, monkeypatch):
    _gpio(sysfs.root, CAM, "out", "1")
    _gpio(sysfs.root, MODEM, "out", "0")
    ops = _ops(monkeypatch)
    status = ops.relay_status(None, None, {})
    assert status["camera"]["state"] == "OFF" and status["modem"]["state"] == "ON"
    assert ops.camera_relay_pin_test(None, None, {"pin": MODEM, "on": True})["ok"] is False
    _gpio(sysfs.root, 357)
    assert ops.camera_relay_pin_test(None, None, {"pin": 357, "on": True})["state"] == "ON"
    ops.cleanup_relay_test_pins(None, None, "exit")
    assert relay_mod.read_relay_state(357) == "OFF" and (sysfs.root / "unexport").read_text() == "357"
    assert relay_mod.read_relay_state(MODEM) == "ON"


def test_new_operations_registered_with_capabilities(tmp_path):
    platform = ops_mod.create_service_platform(base_dir=tmp_path, state_dir=tmp_path / "state")
    for name, cap in {"relay.status": "camera.read", "modem.power.on": "modem.power",
                      "modem.power.test": "modem.power", "camera.relay.pin_test": "camera.reset"}.items():
        assert platform.operations[name].capability == cap
        assert platform.operations[name].handler is not None
    technician = platform.start_session(
        principal=Principal(username="t", role="technician", capabilities=TECHNICIAN_CAPABILITIES),
        grant=EdgeServiceGrantRef(grant_id="TL-GRANT-x", expires_at=9e12),
    )
    with pytest.raises(PermissionError):
        platform.call("modem.power.test", technician)


class _FakePlatform:
    def __init__(self):
        self.calls, self.leases, self.cleaned = [], {}, []
        self.cleanup_handlers = {"CameraPowerLease": lambda *_: self.cleaned.append("camera"),
                                 "DiagnosticLease": lambda *_: self.cleaned.append("pins")}
        self.session = SimpleNamespace(session_id="S1")

    def current_session(self):
        return self.session

    def call(self, op, session, **kw):
        self.calls.append(op)
        if op in {"camera.power.acquire", "camera.detect"}:
            self.leases["CameraPowerLease"] = {"active": True, "session_id": "S1"}
        if op == "camera.relay.pin_test":
            self.leases["DiagnosticLease"] = {"active": True, "session_id": "S1"}
        if op == "camera.power.release":
            self.leases.pop("CameraPowerLease", None)
        return {"ok": True, "camera": {}, "modem": {}}

    def _load(self):
        return {"leases": self.leases}

    def release_lease(self, _s, lease_type, _r):
        self.leases.pop(lease_type, None)


def _run_menu(monkeypatch, tmp_path, inputs, platform=None):
    platform = platform or _FakePlatform()
    monkeypatch.setattr(cli, "_service_platform", lambda _b: platform)
    monkeypatch.setattr(cli, "camera_menu", lambda _b: platform.calls.append("camera_menu"))
    it = iter(inputs)

    def fake_input(_p=""):
        v = next(it)
        if v is KeyboardInterrupt:
            raise KeyboardInterrupt
        return v

    monkeypatch.setattr("builtins.input", fake_input)
    cli.relay_menu(tmp_path)
    return platform


def test_menu_routes_through_service_operations_and_releases(monkeypatch, tmp_path):
    p = _run_menu(monkeypatch, tmp_path, ["2", "6", "357", "j", "8", "9"])
    ops = [c for c in p.calls if c != "relay.status"]
    assert ops == ["camera.power.acquire", "camera.relay.pin_test", "camera.power.acquire", "camera_menu"]
    assert sorted(p.cleaned) == ["camera", "pins"] and not p.leases


def test_menu_releases_on_ctrl_c(monkeypatch, tmp_path):
    p = _run_menu(monkeypatch, tmp_path, ["7", KeyboardInterrupt])
    assert "camera.detect" in p.calls and p.cleaned == ["camera"] and not p.leases


def test_menu_modem_test_needs_confirmation(monkeypatch, tmp_path):
    p = _run_menu(monkeypatch, tmp_path, ["5", "n", "5", "j", "9"])
    assert p.calls.count("modem.power.test") == 1


def test_menu_without_session_and_without_sudo_asks_for_sudo(monkeypatch, tmp_path, capsys):
    p = _FakePlatform()
    p.current_session = lambda: None
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)
    _run_menu(monkeypatch, tmp_path, [], platform=p)
    assert "sudo" in capsys.readouterr().out and p.calls == []


def test_menu_as_root_starts_and_ends_its_own_cli_session(monkeypatch, tmp_path):
    p = _FakePlatform()
    p.current_session = lambda: None
    started, ended = [], []
    p.start_local_cli_session = lambda user: (started.append(user), p.session)[1]
    p.invalidate = lambda session, reason: ended.append(reason)
    monkeypatch.setattr(cli.os, "geteuid", lambda: 0)
    monkeypatch.setenv("SUDO_USER", "orangepi")
    _run_menu(monkeypatch, tmp_path, ["2", "9"], platform=p)
    assert started == ["orangepi"] and ended == ["cli menu exit"]
    assert "camera.power.acquire" in p.calls and p.cleaned == ["camera"]


def test_existing_ui_session_is_reused_and_not_ended(monkeypatch, tmp_path):
    p = _FakePlatform()
    p.start_local_cli_session = lambda user: pytest.fail("must reuse the UI session")
    p.invalidate = lambda *_a: pytest.fail("must not end the UI session")
    _run_menu(monkeypatch, tmp_path, ["9"], platform=p)


def test_local_cli_session_is_audited_senior_technician(tmp_path):
    from service_platform import SENIOR_TECHNICIAN_CAPABILITIES
    platform = ops_mod.create_service_platform(base_dir=tmp_path, state_dir=tmp_path / "run")
    session = platform.start_local_cli_session("orangepi")
    assert session.principal.username == "cli:orangepi" and session.principal.role == "local_cli"
    assert session.capabilities == SENIOR_TECHNICIAN_CAPABILITIES and "system.reboot" not in session.capabilities
    assert platform.current_session().session_id == session.session_id
    audit = Path(platform.audit_path).read_text(encoding="utf-8")
    assert "session.start" in audit and "cli:orangepi" in audit


def test_cli_never_touches_gpio_and_lists_menu():
    src = (ROOT / "edge/tools/bootstrap_cli.py").read_text(encoding="utf-8")
    assert "/sys/class/gpio" not in src and "GPIO.output" not in src
    assert 'print("7. Relaeer (kamera og modem)")' in src and "relay_menu(base_dir)" in src


def test_camera_menu_gets_power_and_releases(monkeypatch, tmp_path):
    p = _FakePlatform()
    monkeypatch.setattr(cli, "_service_platform", lambda _b: p)
    monkeypatch.setattr(cli, "camera_menu", lambda _b: p.calls.append("camera_menu"))
    cli.camera_menu_powered(tmp_path)
    assert p.calls == ["camera.power.acquire", "camera_menu"]
    assert p.cleaned == ["camera"] and not p.leases
    src = (ROOT / "edge/tools/bootstrap_cli.py").read_text(encoding="utf-8")
    assert "camera_menu_powered(base_dir)" in src


def test_camera_menu_without_session_still_opens(monkeypatch, tmp_path, capsys):
    p = _FakePlatform()
    p.current_session = lambda: None
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(cli, "_service_platform", lambda _b: p)
    monkeypatch.setattr(cli, "camera_menu", lambda _b: p.calls.append("camera_menu"))
    cli.camera_menu_powered(tmp_path)
    assert p.calls == ["camera_menu"] and "sudo" in capsys.readouterr().out


def test_agent_stop_keeps_service_session_directory():
    unit = (ROOT / "edge/scripts/timelapse-edge.service").read_text(encoding="utf-8")
    assert "RuntimeDirectory=timelapse" in unit and "RuntimeDirectoryPreserve=yes" in unit


# ── Robustness when the SSH session drops (2026-10-04) ──────────────────────
# Over the agent's own reverse tunnel, pausing the agent kills the session:
# SIGHUP, closed terminal, and (on old units) /run/timelapse — with the lease
# records — removed. The menu must still switch the camera off and restart
# the agent, or a remote Edge on 4G is stranded.

def test_platform_recreates_vanished_state_dir(tmp_path):
    import shutil as _sh
    state = tmp_path / "run"
    platform = ops_mod.create_service_platform(base_dir=tmp_path, state_dir=state)
    _sh.rmtree(state)
    platform._save({"x": 1})
    assert (state / "service_session.json").exists()


def test_release_uses_held_leases_when_state_file_is_gone(monkeypatch, tmp_path):
    p = _FakePlatform()
    p.leases.clear()                      # state file lost while the agent was paused
    cli._release_relay_leases(p, p.session, {"CameraPowerLease"})
    assert p.cleaned == ["camera"]


def test_sighup_releases_camera_and_restarts_agent(monkeypatch, tmp_path):
    import os
    import signal as _signal
    p = _FakePlatform()
    steps = iter(["2", "HUP"])

    def fake_input(_prompt=""):
        v = next(steps)
        if v == "HUP":
            p.leases.clear()             # /run/timelapse removed with the agent
            os.kill(os.getpid(), _signal.SIGHUP)
        return v

    monkeypatch.setattr(cli, "_service_platform", lambda _b: p)
    monkeypatch.setattr("builtins.input", fake_input)
    before = _signal.getsignal(_signal.SIGHUP)
    cli.relay_menu(tmp_path)
    assert p.cleaned == ["camera"]
    assert _signal.getsignal(_signal.SIGHUP) == before   # handler restored


def test_release_survives_closed_terminal(monkeypatch, tmp_path):
    p = _FakePlatform()

    def dead_print(*_a, **_k):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr("builtins.print", dead_print)
    cli._release_relay_leases(p, p.session, {"CameraPowerLease", "DiagnosticLease"})
    assert sorted(p.cleaned) == ["camera", "pins"]


def test_camera_menu_powered_releases_on_hangup(monkeypatch, tmp_path):
    p = _FakePlatform()
    monkeypatch.setattr(cli, "_service_platform", lambda _b: p)

    def hang(_b):
        p.leases.clear()
        raise cli._SessionLost("SIGHUP")

    monkeypatch.setattr(cli, "camera_menu", hang)
    cli.camera_menu_powered(tmp_path)
    assert p.calls[0] == "camera.power.acquire" and p.cleaned == ["camera"]
