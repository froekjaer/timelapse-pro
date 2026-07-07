from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = REPO_ROOT / "headend" / "main.py"


@pytest.mark.smoke
def test_compliance_and_resilience_endpoints_are_present() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")
    assert '@app.get("/api/compliance/cockpit")' in source
    assert '@app.get("/api/compliance/reports/{standard}")' in source
    assert '@app.get("/api/admin/resilience/assessment")' in source
    assert '@app.post("/api/compliance/updates/{update_id}/accept")' in source


@pytest.mark.smoke
def test_compliance_helpers_are_defined() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")
    assert 'def _compliance_approval_state(' in source
    assert 'def _approval_queue(' in source
    assert 'def _control_summary_state(' in source
