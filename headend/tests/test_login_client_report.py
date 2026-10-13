"""Browser-side passkey errors reach the Headend log (2026-10-13)."""
import logging

from fastapi.testclient import TestClient

import main
from api import login_client_report_api as report


def test_report_is_logged_sanitised_and_rate_limited(caplog, monkeypatch):
    monkeypatch.setattr(report, "_recent", {})
    client = TestClient(main.app)
    with caplog.at_level(logging.WARNING, logger="headend"):
        r = client.post("/api/auth/webauthn/client-report", json={
            "stage": "touch-id", "name": "NotAllowedError",
            "message": "The operation is not allowed <script>" + "x" * 500})
    assert r.status_code == 204
    line = next(m for m in caplog.messages if m.startswith("Login client report"))
    assert "stage=touch-id" in line and "name=NotAllowedError" in line
    assert "<script>" not in line and len(line) < 700
    for _ in range(report.MAX_PER_MINUTE + 5):
        client.post("/api/auth/webauthn/client-report", json={"stage": "x"})
    assert len(report._recent["testclient"]) == report.MAX_PER_MINUTE


def test_login_page_reports_touch_id_and_prefetch_errors():
    from pathlib import Path
    page = (Path(__file__).resolve().parents[2] / "timelapse-ui/src/pages/LoginPage.tsx").read_text(encoding="utf-8")
    assert "reportPasskeyError('touch-id', e)" in page and "reportPasskeyError('prefetch', e)" in page
