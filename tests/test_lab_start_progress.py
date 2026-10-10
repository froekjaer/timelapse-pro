"""LAB start feedback step by step (Peter 2026-10-10)."""
import asyncio
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

from services import lab_progress  # noqa: E402


def test_store_filters_by_session_start_and_is_bounded():
    dev = "TL-PROGRESS-1"
    lab_progress.record(dev, "ready", "old session")
    since = (datetime.now(timezone.utc) + timedelta(milliseconds=5)).isoformat()
    import time
    time.sleep(0.01)
    lab_progress.record(dev, "received", "Edgen har modtaget LAB")
    lab_progress.record(dev, "camera_power", "Kameraet tændes", {"warmup_s": 10})
    rows = lab_progress.events(dev, since)
    assert [r["phase"] for r in rows] == ["received", "camera_power"]
    assert rows[1]["extra"] == {"warmup_s": 10}
    for i in range(lab_progress.MAX_EVENTS + 10):
        lab_progress.record(dev, "params", str(i))
    assert len(lab_progress.events(dev)) == lab_progress.MAX_EVENTS


def test_edge_post_uses_device_auth_and_ui_get_requires_user_and_device_access(monkeypatch):
    import edge_sync

    src = (ROOT / "headend/edge_sync.py").read_text(encoding="utf-8")
    post = src.split('@router.post("/lab-progress/{device_id}")', 1)[1].split("@router.", 1)[0]
    assert "Depends(_require_edge_sync_auth)" in post
    get = src.split('@router.get("/lab-progress/{device_id}")', 1)[1]
    assert "_ensure_capture_device_access(db, user, device_id)" in get
    assert "user=Depends(_auth_get_current_user)" in get
    with pytest.raises(Exception) as exc:
        edge_sync.ui_lab_progress("TL-X", None, user=None, db=None)
    assert getattr(exc.value, "status_code", None) == 401
    out = asyncio.run(edge_sync.edge_lab_progress("TL-X", edge_sync.LabProgressReport(phase="received"), None))
    assert out["phase"] == "received"


def test_progress_never_touches_device_config():
    src = (ROOT / "headend/services/lab_progress.py").read_text(encoding="utf-8")
    assert "device_config" not in src.split('"""', 2)[2]       # only mentioned in the docstring


def test_headend_records_tunnel_wake_and_edge_reports_every_step():
    wake = (ROOT / "headend/services/edge_wake.py").read_text(encoding="utf-8")
    assert 'lab_progress.record(device_id, "woken"' in wake
    agent = (ROOT / "edge/agent.py").read_text(encoding="utf-8")
    for phase in ("received", "camera_power", "camera_connecting", "camera_retry", "ready", "params", "camera_failed"):
        assert f'self._lab_progress("{phase}"' in agent, phase


def test_edge_progress_report_is_fire_and_forget():
    sys.path.insert(0, str(ROOT / "edge"))
    import agent as agent_mod

    a = agent_mod.EdgeAgent.__new__(agent_mod.EdgeAgent)
    a._device_id = "TL-X"
    sent = threading.Event()
    a._api = SimpleNamespace(_post=lambda path, payload: (sent.set(), (path, payload))[1])
    a._lab_progress("camera_power", "Kameraet tændes", warmup_s=10)   # returns at once
    assert sent.wait(2)


def test_lab_page_shows_real_steps_not_a_guessed_countdown():
    page = (ROOT / "timelapse-ui/src/pages/LabPage.tsx").read_text(encoding="utf-8")
    assert "<LabStartProgress deviceId={deviceId} since={labProgressSince} />" in page
    assert "configPullS" not in page and "Venter ~" not in page
