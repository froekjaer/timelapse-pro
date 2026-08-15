"""Unit contracts for centrally governed local Edge service access."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import Depends, HTTPException

from headend.api.service_access_api import create_service_access_router


class _Query:
    def __init__(self, device):
        self.device = device

    def filter_by(self, **_filters):
        return self

    def first(self):
        return self.device


class _Db:
    def __init__(self, device):
        self.device = device
        self.commits = 0

    def query(self, _model):
        return _Query(self.device)

    def commit(self):
        self.commits += 1


def _endpoint(events: list):
    router = create_service_access_router(
        require_role=lambda *_roles: Depends(lambda: None),
        ensure_device_access=lambda *_args: None,
        record_siem_events=lambda _db, _device_id, rows: events.extend(rows),
        now_utc=lambda: datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc),
    )
    return next(route.endpoint for route in router.routes if route.path.endswith("/service-access"))


def test_master_switch_disables_lab_and_records_audit_event():
    events = []
    device = SimpleNamespace(
        device_config=json.dumps({"debug_mode": {"enabled": True}, "lab_camera_ready": True}),
        config_version="old",
    )
    db = _Db(device)

    result = _endpoint(events)(
        "TL-TEST",
        {"enabled": False, "live_view_max_duration_s": 600},
        user=SimpleNamespace(username="admin", role="admin", id=1, customer_id=None, on_site_service=False),
        db=db,
    )

    saved = json.loads(device.device_config)
    assert result["service_access"]["enabled"] is False
    assert saved["debug_mode"]["enabled"] is False
    assert saved["debug_mode"]["disabled_reason"] == "central_service_access_disabled"
    assert saved["lab_camera_ready"] is False
    assert events[0]["event_type"] == "service_access_policy_change"
    assert db.commits == 2


def test_continuous_live_view_requires_explicit_policy_but_is_configurable():
    device = SimpleNamespace(device_config="{}", config_version="")
    result = _endpoint([])(
        "TL-TEST",
        {
            "enabled": True,
            "live_view_enabled": True,
            "live_view_max_duration_s": 3600,
            "allow_continuous_live_view": True,
        },
        user=SimpleNamespace(username="admin", role="admin", id=1, customer_id=None, on_site_service=False),
        db=_Db(device),
    )

    assert result["service_access"]["allow_continuous_live_view"] is True
    assert result["service_access"]["live_view_max_duration_s"] == 3600


@pytest.mark.parametrize("value", [29, 86401, "invalid"])
def test_invalid_live_view_maximum_is_rejected(value):
    device = SimpleNamespace(device_config="{}", config_version="")
    with pytest.raises(HTTPException) as error:
        _endpoint([])(
            "TL-TEST",
            {"live_view_max_duration_s": value},
            user=SimpleNamespace(username="admin", role="admin", id=1, customer_id=None, on_site_service=False),
            db=_Db(device),
        )
    assert error.value.status_code == 400
