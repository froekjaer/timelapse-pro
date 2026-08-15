from datetime import datetime, timezone

from edge.agent import EdgeAgent
from edge.utils.database import EdgeDatabase


class _SlotAgent:
    _device_id = "TL-SLOT"

    def __init__(self, cfg=None):
        self._cfg = cfg or {
            "schedule": {
                "capture_mode": "interval",
                "interval_minutes": 60,
                "capture_catchup_seconds": 120,
            }
        }

    _scheduled_capture_slot = EdgeAgent._scheduled_capture_slot
    _should_capture = EdgeAgent._should_capture
    _slot_payload = EdgeAgent._slot_payload
    _to_local = staticmethod(EdgeAgent._to_local)
    _parse_time = staticmethod(EdgeAgent._parse_time)

    def _camera_warmup_seconds(self):
        return 10


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def test_lead_window_claims_next_scheduled_slot():
    agent = _SlotAgent()

    slot = agent._scheduled_capture_slot(utc("2026-08-15T09:59:50"), "interval")

    assert slot["scheduled_at"] == utc("2026-08-15T10:00:00")
    assert slot["slot_id"] == "TL-SLOT:interval:2026-08-15T10:00:00+00:00"


def test_boundary_crossing_is_same_slot_not_next_attempt(tmp_path):
    db = EdgeDatabase({"storage": {"db_path": str(tmp_path / "edge.db")}})
    agent = _SlotAgent()
    before = agent._scheduled_capture_slot(utc("2026-08-15T09:59:50"), "interval")
    after = agent._scheduled_capture_slot(utc("2026-08-15T10:00:05"), "interval")

    assert before["slot_id"] == after["slot_id"]
    assert db.claim_capture_slot(
        slot_id=before["slot_id"],
        device_id="TL-SLOT",
        mode="interval",
        scheduled_at=before["scheduled_at"],
    )
    assert not db.claim_capture_slot(
        slot_id=after["slot_id"],
        device_id="TL-SLOT",
        mode="interval",
        scheduled_at=after["scheduled_at"],
    )


def test_capture_failure_marks_slot_attempted_once(tmp_path):
    db = EdgeDatabase({"storage": {"db_path": str(tmp_path / "edge.db")}})
    agent = _SlotAgent()
    slot = agent._scheduled_capture_slot(utc("2026-08-15T10:00:05"), "interval")

    assert db.claim_capture_slot(slot_id=slot["slot_id"], device_id="TL-SLOT", mode="interval", scheduled_at=slot["scheduled_at"])
    db.complete_capture_slot(slot_id=slot["slot_id"], status="failed", error="camera busy")

    assert not db.claim_capture_slot(slot_id=slot["slot_id"], device_id="TL-SLOT", mode="interval", scheduled_at=slot["scheduled_at"])
    assert db.capture_slot(slot["slot_id"])["status"] == "failed"


def test_reboot_catch_up_claims_missed_slot_once(tmp_path):
    db = EdgeDatabase({"storage": {"db_path": str(tmp_path / "edge.db")}})
    agent = _SlotAgent()
    slot = agent._scheduled_capture_slot(utc("2026-08-15T10:01:30"), "interval")

    assert slot["scheduled_at"] == utc("2026-08-15T10:00:00")
    assert db.claim_capture_slot(slot_id=slot["slot_id"], device_id="TL-SLOT", mode="interval", scheduled_at=slot["scheduled_at"])

    db_after_reboot = EdgeDatabase({"storage": {"db_path": str(tmp_path / "edge.db")}})
    same_slot = agent._scheduled_capture_slot(utc("2026-08-15T10:01:45"), "interval")
    assert same_slot["slot_id"] == slot["slot_id"]
    assert not db_after_reboot.claim_capture_slot(
        slot_id=same_slot["slot_id"],
        device_id="TL-SLOT",
        mode="interval",
        scheduled_at=same_slot["scheduled_at"],
    )


def test_long_capture_crossing_boundary_does_not_create_second_attempt(tmp_path):
    db = EdgeDatabase({"storage": {"db_path": str(tmp_path / "edge.db")}})
    agent = _SlotAgent()
    slot = agent._scheduled_capture_slot(utc("2026-08-15T09:59:50"), "interval")
    assert db.claim_capture_slot(slot_id=slot["slot_id"], device_id="TL-SLOT", mode="interval", scheduled_at=slot["scheduled_at"])

    after_long_capture = agent._scheduled_capture_slot(utc("2026-08-15T10:00:45"), "interval")
    assert after_long_capture["slot_id"] == slot["slot_id"]
    assert not db.claim_capture_slot(
        slot_id=after_long_capture["slot_id"],
        device_id="TL-SLOT",
        mode="interval",
        scheduled_at=after_long_capture["scheduled_at"],
    )


def test_fixed_schedule_timezone_is_stored_as_utc_slot():
    agent = _SlotAgent({
        "schedule": {
            "capture_mode": "fixed",
            "timezone": "Europe/Copenhagen",
            "capture_times": ["12:00"],
            "capture_catchup_seconds": 120,
        }
    })

    slot = agent._scheduled_capture_slot(utc("2026-08-15T09:59:50"), "fixed")

    assert slot["scheduled_at"] == utc("2026-08-15T10:00:00")
    assert slot["slot_id"] == "TL-SLOT:fixed:2026-08-15T10:00:00+00:00"


def test_outside_catch_up_window_is_not_due():
    agent = _SlotAgent()

    assert agent._scheduled_capture_slot(utc("2026-08-15T10:03:00"), "interval") is None
