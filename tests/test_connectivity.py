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
