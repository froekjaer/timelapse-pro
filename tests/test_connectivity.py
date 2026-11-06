"""Phase 3: unit tests for the central authoritative connectivity calculation.

Regression anchor: a persisted status="online" whose last observation is hours
old MUST compute as offline (the Edge2 defect). Pure functions; no DB/HTTP.

The CMDB/ITIM "consistency" tests below exercise the shared connectivity
functions and CMDB's delegation to them. They are NOT HTTP integration tests
(no server, no requests); end-to-end HTTP consistency is a separate,
integration-marked concern.
"""
from datetime import datetime, timedelta, timezone

import pytest

import connectivity as C

NOW = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)


def ago(seconds):
    return NOW - timedelta(seconds=seconds)


def test_connectivity_state_thresholds():
    assert C.connectivity_state(ago(0), NOW) == "online"
    assert C.connectivity_state(ago(599), NOW) == "online"
    assert C.connectivity_state(ago(600), NOW) == "online"     # boundary <= 10 min
    assert C.connectivity_state(ago(601), NOW) == "stale"
    assert C.connectivity_state(ago(900), NOW) == "stale"      # boundary <= 15 min
    assert C.connectivity_state(ago(901), NOW) == "offline"
    assert C.connectivity_state(None, NOW) == "unknown"


def test_future_receipt_is_unknown_not_online():
    # Clock skew / replay: a future receipt time must never read as online.
    assert C.connectivity_state(NOW + timedelta(seconds=30), NOW) == "unknown"


def test_naive_datetime_treated_as_utc():
    assert C.connectivity_state(datetime(2026, 11, 3, 11, 59, 0), NOW) == "online"


def test_is_up_online_and_stale_are_up_offline_is_not():
    assert C.is_up(ago(0), NOW) is True
    assert C.is_up(ago(700), NOW) is True      # stale still counts as up
    assert C.is_up(ago(1000), NOW) is False
    assert C.is_up(None, NOW) is False


class _Dev:
    def __init__(self, status=None, last_seen=None):
        self.status = status
        self.last_seen = last_seen


def test_display_status_passthrough_lifecycle_states():
    # Only genuine administrative/lifecycle states pass through regardless of age.
    for st in ("provisioning", "import"):
        assert C.display_status(_Dev(status=st, last_seen=ago(10_000_000)), NOW) == st


def test_unknown_or_missing_status_does_not_mask_fresh_connectivity():
    # "unknown"/None/"" is the ABSENCE of a lifecycle state, not a state: a fresh
    # authenticated last_seen must compute connectivity, not be masked as unknown.
    for st in ("unknown", None, "", "online", "offline"):
        assert C.display_status(_Dev(status=st, last_seen=ago(60)), NOW) == "online"
    # ...with no observation at all it is still unknown (no evidence):
    assert C.display_status(_Dev(status="unknown", last_seen=None), NOW) == "unknown"
    # a persisted "online" that is stale must read stale/offline, never online:
    assert C.display_status(_Dev(status="online", last_seen=ago(700)), NOW) == "stale"
    assert C.display_status(_Dev(status="online", last_seen=ago(100000)), NOW) == "offline"


def test_display_status_none_device():
    assert C.display_status(None, NOW) == "unknown"


def test_display_status_never_seen_is_unknown_and_consistent():
    # P2: never-seen unifies with connectivity_state(None) -> "unknown" (not "offline").
    dev = _Dev(status="online", last_seen=None)
    assert C.connectivity_state(None, NOW) == "unknown"
    assert C.display_status(dev, NOW) == "unknown"
    assert C.is_up(None, NOW) is False


def test_display_status_fresh_is_online():
    assert C.display_status(_Dev(status="online", last_seen=ago(60)), NOW) == "online"


def test_edge2_regression_persisted_online_but_stale_is_offline():
    # Edge2 (TL-043EB9E72EFD): status persisted "online", last observed ~87h ago.
    dev = _Dev(status="online", last_seen=ago(87 * 3600))
    assert C.display_status(dev, NOW) == "offline"


def test_status_changes_as_time_passes_without_new_message():
    dev = _Dev(status="online", last_seen=NOW)
    assert C.display_status(dev, NOW) == "online"
    assert C.display_status(dev, NOW + timedelta(minutes=12)) == "stale"
    assert C.display_status(dev, NOW + timedelta(minutes=20)) == "offline"


def test_thresholds_are_configurable(monkeypatch):
    monkeypatch.setattr(C, "ONLINE_MAX_AGE_S", 60)
    monkeypatch.setattr(C, "OFFLINE_MIN_AGE_S", 120)
    assert C.connectivity_state(ago(30), NOW) == "online"
    assert C.connectivity_state(ago(90), NOW) == "stale"
    assert C.connectivity_state(ago(130), NOW) == "offline"


def test_future_timestamp_is_not_up():
    # P1/ITIM: a future receipt time -> unknown -> NOT up.
    future = NOW + timedelta(seconds=120)
    assert C.connectivity_state(future, NOW) == "unknown"
    assert C.is_up(future, NOW) is False


# --- P4: threshold validation (misconfiguration must not silently mislead) ---

def test_resolve_thresholds_valid():
    assert C._resolve_thresholds("300", "600") == (300, 600)


def test_resolve_thresholds_non_integer_falls_back():
    assert C._resolve_thresholds("abc", "600") == (C._DEFAULT_ONLINE_S, 600)
    assert C._resolve_thresholds("300", "x") == (300, C._DEFAULT_OFFLINE_S)


def test_resolve_thresholds_non_positive_falls_back():
    assert C._resolve_thresholds("0", "600") == (C._DEFAULT_ONLINE_S, 600)
    assert C._resolve_thresholds("-5", "600") == (C._DEFAULT_ONLINE_S, 600)


def test_resolve_thresholds_incoherent_order_falls_back_to_defaults():
    assert C._resolve_thresholds("1000", "500") == (C._DEFAULT_ONLINE_S, C._DEFAULT_OFFLINE_S)


def test_resolve_thresholds_none_uses_default():
    assert C._resolve_thresholds(None, None) == (C._DEFAULT_ONLINE_S, C._DEFAULT_OFFLINE_S)


# --- P5: CMDB / API / ITIM consistency across the five scenarios ---

_SCEN = {
    "fresh":   _Dev("online", NOW - timedelta(seconds=60)),
    "stale":   _Dev("online", NOW - timedelta(seconds=700)),
    "offline": _Dev("online", NOW - timedelta(hours=87)),
    "future":  _Dev("online", NOW + timedelta(seconds=120)),
    "never":   _Dev("online", None),
}
_EXPECT = {"fresh": "online", "stale": "stale", "offline": "offline",
           "future": "unknown", "never": "unknown"}


def test_shared_display_status_matches_expected_for_all_scenarios():
    # Function-level (the value the API layer returns), not an HTTP call.
    for k, dev in _SCEN.items():
        assert C.display_status(dev, NOW) == _EXPECT[k], k


def test_itim_is_up_consistent_with_display_status():
    for k, dev in _SCEN.items():
        assert C.is_up(dev.last_seen, NOW) == (C.display_status(dev, NOW) in ("online", "stale")), k


def test_cmdb_delegates_to_the_same_calculation():
    # Consistency of the CMDB surface with the single source of truth, using
    # wall-clock now (cmdb._display_device_status has no now override).
    cmdb = pytest.importorskip("cmdb")
    from datetime import datetime as _dt, timezone as _tz
    now = _dt.now(_tz.utc)
    cases = {
        "fresh":   _Dev("online", now - timedelta(seconds=60)),
        "stale":   _Dev("online", now - timedelta(seconds=700)),
        "offline": _Dev("online", now - timedelta(hours=87)),
        "never":   _Dev("online", None),
        "import":  _Dev("import", None),
        "provisioning": _Dev("provisioning", None),
        "unknown_fresh": _Dev("unknown", now - timedelta(seconds=60)),
    }
    for k, dev in cases.items():
        assert cmdb._display_device_status(dev) == C.display_status(dev), k


# --- P6: Codex review follow-ups (two regressions) ---------------------------

# Finding 2 (lifecycle): the terminal administrative states ``revoked`` and
# ``retired`` (written to device.status by the edge lifecycle) must keep their
# meaning and must NEVER be masked by a freshly computed connectivity status.

def test_revoked_and_retired_are_not_masked_by_fresh_connectivity():
    for st in ("revoked", "retired"):
        # A fresh last_seen would otherwise compute "online" -> must stay the admin state.
        assert C.display_status(_Dev(status=st, last_seen=ago(60)), NOW) == st
        # ...and at any age, including never-seen.
        assert C.display_status(_Dev(status=st, last_seen=ago(10_000_000)), NOW) == st
        assert C.display_status(_Dev(status=st, last_seen=None), NOW) == st
        assert st in C.LIFECYCLE_STATES


def test_revoked_retired_consistent_via_cmdb():
    cmdb = pytest.importorskip("cmdb")
    now = datetime.now(timezone.utc)
    for st in ("revoked", "retired"):
        dev = _Dev(st, now - timedelta(seconds=60))
        assert cmdb._display_device_status(dev) == st == C.display_status(dev)


# Finding 1 (ITIM): the edge "up" / "last_seen_age_s" metrics must derive from
# the device's AUTHORITATIVE last_seen, not the diagnostics recorded_at. The
# diagnostics-row age must remain available on its own, as ``diag_age_s``.
# Driven with a single stubbed diagnostics row -- no DB / Postgres. Uses the
# real wall clock (not NOW) so it stays consistent with connectivity.is_up,
# which reads the clock itself.

def _run_itim_edge_probe(last_seen_age_s, recorded_age_s, monkeypatch):
    itim = pytest.importorskip("itim")
    ref = datetime.now(timezone.utc)
    dev_last_seen = None if last_seen_age_s is None else ref - timedelta(seconds=last_seen_age_s)
    recorded_at = ref - timedelta(seconds=recorded_age_s)
    captured = {}

    class _Res:
        def __init__(self, rows):
            self._rows = rows
        def mappings(self):
            return self
        def all(self):
            return self._rows

    row = {
        "device_id": "TL-TEST", "recorded_at": recorded_at, "dev_last_seen": dev_last_seen,
        "cpu_temp_c": 40.0, "cpu_load_pct": 10.0, "ram_used_mb": 100.0, "disk_used_gb": 1.0,
        "battery_v": 12.5, "solar_v": 18.0, "connectivity": None, "uptime_s": 1000.0,
        "ssd_used_pct": 10.0, "upload_queue": 0.0, "cam_battery_pct": 90.0,
        "cam_shutter_pct": 1.0, "cam_shutter_alarm": False, "cam_available_shots": 1000.0,
    }

    class _DB:
        def execute(self, *a, **k):
            return _Res([row])

    monkeypatch.setattr(itim, "record_metrics", lambda db, key, kind, m, **kw: captured.update(m))
    monkeypatch.setattr(itim, "set_health", lambda *a, **k: None)
    monkeypatch.setattr(itim, "_setting", lambda *a, **k: "11.8")
    itim._probe_edge_from_diagnostics(_DB())
    return captured


def test_itim_up_follows_last_seen_not_recorded_at(monkeypatch):
    # Fresh diagnostics ROW but device last_seen is 87h stale -> NOT up (offline).
    # last_seen_age_s reflects last_seen; diagnostics age kept separately.
    m = _run_itim_edge_probe(last_seen_age_s=87 * 3600, recorded_age_s=0, monkeypatch=monkeypatch)
    assert m["up"] == 0.0
    assert m["last_seen_age_s"] == pytest.approx(87 * 3600, abs=30)
    assert m["diag_age_s"] == pytest.approx(0, abs=30)


def test_itim_up_online_when_last_seen_fresh_despite_old_diagnostics(monkeypatch):
    # Inverse: stale diagnostics ROW but a fresh authenticated last_seen -> up.
    m = _run_itim_edge_probe(last_seen_age_s=60, recorded_age_s=87 * 3600, monkeypatch=monkeypatch)
    assert m["up"] == 1.0
    assert m["last_seen_age_s"] == pytest.approx(60, abs=30)
    assert m["diag_age_s"] == pytest.approx(87 * 3600, abs=30)


def test_itim_up_unknown_when_last_seen_missing(monkeypatch):
    # No authoritative last_seen -> no verified liveness -> not up; no last_seen_age_s,
    # but diagnostics age is still exposed.
    m = _run_itim_edge_probe(last_seen_age_s=None, recorded_age_s=0, monkeypatch=monkeypatch)
    assert m["up"] == 0.0
    assert "last_seen_age_s" not in m
    assert m["diag_age_s"] == pytest.approx(0, abs=30)
