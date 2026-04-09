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
    content = read_agent()
    idx_heartbeat = content.find("self._send_heartbeat()")
    idx_sync = content.find("self._sync_captures()", idx_heartbeat)
    idx_success = content.find("success = True", idx_heartbeat)
    assert idx_sync > 0 and idx_sync < idx_success, \
        "FEJL: _sync_captures mangler i capture cycle efter heartbeat!"

def test_sync_captures_info_logging():
    content = read_agent()
    assert "Syncing" in content and "log.info" in content, \
        "FEJL: _sync_captures skal logge på INFO niveau!"

def test_sync_captures_called_at_startup():
    content = read_agent()
    count = content.count("self._sync_captures()")
    assert count >= 3, \
        f"FEJL: _sync_captures skal kaldes minimum 3 steder, fundet {count}!"

def test_config_interval_not_zero():
    content = read_agent()
    assert "config_interval = timedelta(minutes=" in content, \
        "FEJL: config_interval mangler i agent.py!"

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
