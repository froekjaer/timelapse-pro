"""_forget_bluetooth_peer_for_ip() — runtime coverage for a real bug found
while assembling this PR: the function calls re.fullmatch() but edge/scripts/
totp-service.py never imported `re`. Every existing test only reads this file
as source text (read_text() contract assertions), so nothing would have
caught a NameError raised the first time a session actually timed out or
/logout was hit. This test imports and calls the function for real.
"""
import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "edge" / "scripts" / "totp-service.py"


def _load_totp_service():
    os.environ["TIMELAPSE_EDGE_ROOT"] = str(ROOT / "edge")
    spec = importlib.util.spec_from_file_location("totp_service_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_forget_bluetooth_peer_removes_the_matching_lease_owner(tmp_path, monkeypatch):
    totp_service = _load_totp_service()

    lease_file = tmp_path / "dnsmasq.leases"
    lease_file.write_text(
        "1234567890 aa:bb:cc:dd:ee:ff 192.168.43.10 some-technician-phone *\n"
    )

    real_path_cls = totp_service.Path

    def fake_path(candidate):
        if str(candidate) == "/var/lib/misc/dnsmasq.leases":
            return real_path_cls(lease_file)
        return real_path_cls("/nonexistent/does-not-exist-for-this-test")

    monkeypatch.setattr(totp_service, "Path", fake_path)

    calls = []

    def fake_run(argv, check=False, capture_output=False):
        calls.append(argv)
        class _Result:
            returncode = 0
        return _Result()

    monkeypatch.setattr(totp_service.subprocess, "run", fake_run)

    # This is the exact call path that previously raised NameError: name 're'
    # is not defined, at the `re.fullmatch(...)` line.
    totp_service._forget_bluetooth_peer_for_ip("192.168.43.10")

    assert calls == [["bluetoothctl", "remove", "AA:BB:CC:DD:EE:FF"]]


def test_forget_bluetooth_peer_is_a_noop_when_no_lease_file_exists(monkeypatch):
    totp_service = _load_totp_service()

    calls = []
    monkeypatch.setattr(
        totp_service.subprocess, "run",
        lambda *a, **k: calls.append(a) or None,
    )

    # Neither candidate lease path exists on this machine — must not raise.
    totp_service._forget_bluetooth_peer_for_ip("192.168.43.10")

    assert calls == []
