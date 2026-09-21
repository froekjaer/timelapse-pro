"""Contract tests that headend/itim.py and headend/siem.py actually call
into headend/maintenance_window.py in the right place, for the right
narrow condition — added alongside the planned-maintenance suppression
feature (2026-09-21, see HANDOVER_LOG.md). The suppression logic itself
(marker parsing, fail-open behaviour) is unit-tested directly in
tests/test_maintenance_window.py; these tests only guard the wiring,
matching this repo's existing style for these two files (see
tests/test_itim_notification_contract.py, tests/test_siem_log_console_contract.py).
"""

from pathlib import Path

ROOT = Path(__file__).parents[1]
ITIM = (ROOT / "headend" / "itim.py").read_text()
SIEM = (ROOT / "headend" / "siem.py").read_text()


def test_itim_suppresses_notify_only_for_up_metric_rules_during_maintenance() -> None:
    start = ITIM.index("def _notify_alert(")
    end = ITIM.index("key = (target.target_key, rule.metric,", start)
    section = ITIM[start:end]

    assert 'rule.metric == "up"' in section
    assert "from maintenance_window import is_maintenance_window_active" in section
    assert "is_maintenance_window_active()" in section
    assert "return" in section
    # Must not gate on anything broader (e.g. resource alerts like RAM/disk
    # must never be suppressed) — the only metric name mentioned is "up".
    assert 'rule.metric ==' in section and section.count('rule.metric ==') == 1


def test_itim_notify_still_runs_for_non_up_metrics_after_the_gate() -> None:
    """The suppression check must be an early-return guard, not wrap the
    whole function — cooldown/notify logic must still be reachable."""
    start = ITIM.index("def _notify_alert(")
    end = ITIM.index("\n\n\n", start)
    section = ITIM[start:end]

    gate_pos = section.index('rule.metric == "up"')
    cooldown_pos = section.index("_notify_cooldown")
    notify_call_pos = section.index("notify({")
    assert gate_pos < cooldown_pos < notify_call_pos


def test_siem_suppresses_notify_only_for_connectivity_category_during_maintenance() -> None:
    start = SIEM.index("async def ingest_events(")
    end = SIEM.index("return result", start)
    section = SIEM[start:end]

    assert 'norm.get("category") == "connectivity"' in section
    assert "from maintenance_window import is_maintenance_window_active" in section
    assert "is_maintenance_window_active()" in section
    assert "continue" in section


def test_siem_notify_still_runs_for_non_connectivity_categories_after_the_gate() -> None:
    start = SIEM.index("async def ingest_events(")
    end = SIEM.index("return result", start)
    section = SIEM[start:end]

    gate_pos = section.index('norm.get("category") == "connectivity"')
    notify_call_pos = section.index("notify({")
    assert gate_pos < notify_call_pos
