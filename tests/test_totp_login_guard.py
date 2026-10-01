"""Single-use TOTP + clock-at-login for the Edge local management login
(added 2026-10-01, Peter). See edge/totp_login_guard.py for the rationale."""
import importlib.util
import sys
import time
from pathlib import Path

import pyotp
import pytest

EDGE = Path(__file__).resolve().parents[1] / "edge"
sys.path.insert(0, str(EDGE))

from totp_login_guard import TotpLoginGuard  # noqa: E402
from totp_verifier import matching_steps, verify_totp  # noqa: E402

SECRET = pyotp.random_base32()


def test_dependency_free_verifier_matches_pyotp():
    totp = pyotp.TOTP(SECRET)
    now = time.time()
    for offset in (-90, -30, 0, 30, 90):
        assert verify_totp(SECRET, totp.at(now + offset), now=now, window=3)
    assert not verify_totp(SECRET, totp.at(now + 200), now=now, window=3)
    assert matching_steps(SECRET, totp.at(now), now=now, window=3)[0] == int(now // 30)


def test_code_is_single_use(tmp_path):
    guard = TotpLoginGuard(tmp_path / "state.json")
    now = time.time()
    code = pyotp.TOTP(SECRET).at(now)
    assert guard.verify_and_consume(SECRET, code, now, 3) is not None
    assert guard.verify_and_consume(SECRET, code, now, 3) is None


def test_older_step_rejected_after_newer(tmp_path):
    guard = TotpLoginGuard(tmp_path / "state.json")
    now = time.time()
    totp = pyotp.TOTP(SECRET)
    assert guard.verify_and_consume(SECRET, totp.at(now), now, 3) is not None
    assert guard.verify_and_consume(SECRET, totp.at(now - 60), now, 3) is None


def test_state_shared_across_instances(tmp_path):
    """Web login and Bluetooth technician service use separate processes but
    the same state file: a code consumed by one is rejected by the other."""
    path = tmp_path / "state.json"
    now = time.time()
    code = pyotp.TOTP(SECRET).at(now)
    assert TotpLoginGuard(path).verify_and_consume(SECRET, code, now, 3) is not None
    assert TotpLoginGuard(path).verify_and_consume(SECRET, code, now, 3) is None


def test_clock_floor_and_browser_time(tmp_path):
    guard = TotpLoginGuard(tmp_path / "state.json")
    now = time.time()
    assert guard.verify_and_consume(SECRET, pyotp.TOTP(SECRET).at(now), now, 3) is not None
    assert guard.clock_floor() >= now - 30
    assert guard.browser_time_acceptable(now)[0]
    assert not guard.browser_time_acceptable(now - 3600)[0]      # before last known good time
    assert not guard.browser_time_acceptable(946684800)[0]      # year 2000: implausible


# ── /verify end-to-end ────────────────────────────────────────────────────
@pytest.fixture()
def svc(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "edge" / "scripts" / "totp-service.py"
    spec = importlib.util.spec_from_file_location("totp_service_clock_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["totp_service_clock_under_test"] = mod
    spec.loader.exec_module(mod)
    cfg = {"totp": {"secret": SECRET, "sid": "cam-test", "valid_window": 3, "enabled": True},
           "management": {"session_timeout": 3600}}
    monkeypatch.setattr(mod, "load_config", lambda: cfg)
    monkeypatch.setattr(mod, "LOGIN_GUARD", TotpLoginGuard(tmp_path / "state.json"))
    monkeypatch.setattr(mod, "_iptables_add", lambda ip: None)
    monkeypatch.setattr(mod, "_get_time_status", lambda: {"synced": False, "source": "x", "offset_ms": None, "stratum": None})
    monkeypatch.setattr(mod, "_systemd_ntp_active", lambda: False)
    calls = []
    monkeypatch.setattr(mod, "_set_system_time_utc", lambda epoch: calls.append(epoch) or (True, "set"))
    mod.AUTH_FAILURES.clear()
    from fastapi.testclient import TestClient
    return mod, TestClient(mod.app, base_url="https://testserver"), calls


def test_verify_replay_rejected(svc):
    mod, client, _ = svc
    code = pyotp.TOTP(SECRET).now()
    assert client.post("/verify", data={"code": code}, follow_redirects=False).status_code == 303
    assert client.post("/verify", data={"code": code}, follow_redirects=False).status_code == 401


def test_set_clock_with_code_valid_at_browser_time(svc):
    mod, client, calls = svc
    browser = time.time() + 3600   # Edge clock is an hour behind
    code = pyotp.TOTP(SECRET).at(browser)
    r = client.post("/verify", data={"code": code, "client_epoch": f"{browser:.3f}", "set_clock": "1"}, follow_redirects=False)
    assert r.status_code == 303
    assert calls and abs(calls[0] - browser) < 1


def test_set_clock_rejects_code_valid_only_at_edge_time(svc):
    mod, client, calls = svc
    browser = time.time() + 3600
    code = pyotp.TOTP(SECRET).now()
    r = client.post("/verify", data={"code": code, "client_epoch": f"{browser:.3f}", "set_clock": "1"}, follow_redirects=False)
    assert r.status_code == 401 and not calls


def test_set_clock_refused_when_clock_synced(svc, monkeypatch):
    mod, client, calls = svc
    monkeypatch.setattr(mod, "_get_time_status", lambda: {"synced": True})
    browser = time.time() + 3600
    r = client.post("/verify", data={"code": pyotp.TOTP(SECRET).at(browser), "client_epoch": f"{browser:.3f}", "set_clock": "1"}, follow_redirects=False)
    assert r.status_code == 409 and not calls


def test_set_clock_refused_before_last_known_good_time(svc):
    mod, client, calls = svc
    now = time.time()
    assert client.post("/verify", data={"code": pyotp.TOTP(SECRET).at(now)}, follow_redirects=False).status_code == 303
    past = now - 7200
    r = client.post("/verify", data={"code": pyotp.TOTP(SECRET).at(past), "client_epoch": f"{past:.3f}", "set_clock": "1"}, follow_redirects=False)
    assert r.status_code == 400 and not calls


def test_login_page_shows_edge_clock(svc):
    mod, client, _ = svc
    page = client.get("/").text
    assert 'id="edge-clock"' in page and "Edge-ur:" in page and 'name="client_epoch"' in page
