"""
TimeLapse Pro — Agent Integrity Tests
"""

AGENT_PATH = "edge/agent.py"

def read_agent():
    return open(AGENT_PATH).read()

def test_sync_captures_limit_100():
    content = read_agent()
    assert "get_unsynced_captures(limit=100)" in content, \
        "FEJL: _sync_captures limit skal være 100!"

def test_sync_captures_in_capture_cycle():
    # 2026-08-24: the per-capture self._send_heartbeat() call was removed —
    # it duplicated the consolidated sync poll and bypassed both poll-interval
    # settings (see test_edge_sync_poll_consolidation.py). _sync_captures()
    # must still run in the capture cycle, just no longer anchored to it.
    content = read_agent()
    cycle_body = content.split("def _do_capture_cycle(", 1)[1].split("\n    def ", 1)[0]
    idx_sync = cycle_body.find("self._sync_captures()")
    idx_success = cycle_body.find("success = True")
    assert idx_sync > 0 and idx_sync < idx_success, \
        "FEJL: _sync_captures mangler i capture cycle før success = True!"

def test_sync_captures_info_logging():
    content = read_agent()
    assert "Syncing" in content and "log.info" in content, \
        "FEJL: _sync_captures skal logge på INFO niveau!"

def test_sync_captures_called_at_startup():
    content = read_agent()
    count = content.count("self._sync_captures()")
    assert count >= 3, \
        f"FEJL: _sync_captures skal kaldes minimum 3 steder, fundet {count}!"

def test_sync_poll_interval_not_zero():
    # 2026-08-19: config-pull, heartbeat and SIEM-forward were consolidated
    # into one sync_interval-gated poll — see edge_agent._run_sync() and
    # Dokumentation/HANDOVER_LOG.md 2026-08-19.
    content = read_agent()
    assert "sync_interval = timedelta(minutes=" in content, \
        "FEJL: sync_interval mangler i agent.py!"

def test_check_update_exists():
    content = read_agent()
    assert "def _check_update" in content, \
        "FEJL: _check_update metode mangler!"

def test_check_update_skips_lab_mode():
    content = read_agent()
    assert "LAB mode aktiv" in content or "enabled" in content, \
        "FEJL: _check_update skal tjekke for LAB mode!"

def test_camera_ready_signal_sent():
    content = read_agent()
    assert "camera-ready" in content, \
        "FEJL: camera-ready signal mangler!"
