"""Tests for headend/maintenance_window.py — the planned-maintenance alert
suppression added 2026-09-21 for the nightly full-server-reboot rehearsal
(see Dokumentation/HANDOVER_LOG.md same date).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "headend"))

from maintenance_window import is_maintenance_window_active  # noqa: E402


def _fixed_now() -> datetime:
    return datetime(2026, 9, 21, 3, 0, 0, tzinfo=UTC)


def test_no_marker_file_is_not_a_maintenance_window(tmp_path, monkeypatch):
    monkeypatch.setattr("maintenance_window.MAINTENANCE_MARKER_PATH", tmp_path / "does-not-exist")
    assert is_maintenance_window_active(now=_fixed_now()) is False


def test_future_expiry_is_an_active_window(tmp_path, monkeypatch):
    marker = tmp_path / "maintenance-until"
    marker.write_text("2026-09-21T03:20:00Z")
    monkeypatch.setattr("maintenance_window.MAINTENANCE_MARKER_PATH", marker)

    assert is_maintenance_window_active(now=_fixed_now()) is True


def test_past_expiry_is_not_an_active_window(tmp_path, monkeypatch):
    marker = tmp_path / "maintenance-until"
    marker.write_text("2026-09-21T02:40:00Z")  # 20 minutes before "now"
    monkeypatch.setattr("maintenance_window.MAINTENANCE_MARKER_PATH", marker)

    assert is_maintenance_window_active(now=_fixed_now()) is False


def test_exact_expiry_instant_is_not_active(tmp_path, monkeypatch):
    """now == expiry must not be treated as still active (strict <)."""
    marker = tmp_path / "maintenance-until"
    marker.write_text("2026-09-21T03:00:00Z")  # exactly equal to _fixed_now()
    monkeypatch.setattr("maintenance_window.MAINTENANCE_MARKER_PATH", marker)

    assert is_maintenance_window_active(now=_fixed_now()) is False


def test_malformed_timestamp_fails_open(tmp_path, monkeypatch):
    marker = tmp_path / "maintenance-until"
    marker.write_text("not-a-timestamp")
    monkeypatch.setattr("maintenance_window.MAINTENANCE_MARKER_PATH", marker)

    assert is_maintenance_window_active(now=_fixed_now()) is False


def test_empty_file_fails_open(tmp_path, monkeypatch):
    marker = tmp_path / "maintenance-until"
    marker.write_text("")
    monkeypatch.setattr("maintenance_window.MAINTENANCE_MARKER_PATH", marker)

    assert is_maintenance_window_active(now=_fixed_now()) is False


def test_naive_timestamp_in_marker_is_treated_as_utc(tmp_path, monkeypatch):
    marker = tmp_path / "maintenance-until"
    marker.write_text("2026-09-21T03:20:00")  # no trailing Z, no offset
    monkeypatch.setattr("maintenance_window.MAINTENANCE_MARKER_PATH", marker)

    assert is_maintenance_window_active(now=_fixed_now()) is True


def test_naive_now_argument_is_treated_as_utc(tmp_path, monkeypatch):
    marker = tmp_path / "maintenance-until"
    marker.write_text("2026-09-21T03:20:00Z")
    monkeypatch.setattr("maintenance_window.MAINTENANCE_MARKER_PATH", marker)

    naive_now = datetime(2026, 9, 21, 3, 0, 0)  # no tzinfo
    assert is_maintenance_window_active(now=naive_now) is True


def test_default_now_uses_real_current_time(tmp_path, monkeypatch):
    marker = tmp_path / "maintenance-until"
    far_future = (datetime.now(UTC) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    marker.write_text(far_future)
    monkeypatch.setattr("maintenance_window.MAINTENANCE_MARKER_PATH", marker)

    assert is_maintenance_window_active() is True  # no `now=` passed at all
