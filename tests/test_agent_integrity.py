"""
TimeLapse Pro — Agent Integrity Tests
======================================
Verificerer at agent.py indeholder kritiske funktioner korrekt.
Kør: pytest tests/test_agent_integrity.py -v
"""

AGENT_PATH = "edge/agent.py"

def read_agent():
    return open(AGENT_PATH).read()

def test_sync_captures_limit_100():
    """_sync_captures skal bruge limit=100 ikke 20."""
    content = read_agent()
    assert "get_unsynced_captures(limit=100)" in content, \
        "FEJL: _sync_captures limit skal være 100!"

def test_sync_captures_in_capture_cycle():
    """_sync_captures skal kaldes direkte i capture cycle efter heartbeat."""
    content = read_agent()
    idx_heartbeat = content.find("self._send_heartbeat()")
    idx_sync = content.find("self._sync_captures()", idx_heartbeat)
    idx_success = content.find("success = True", idx_heartbeat)
    assert idx_sync > 0 and idx_sync < idx_success, \
        "FEJL: _sync_captures mangler i capture cycle efter heartbeat!"

def test_sync_captures_info_logging():
    """_sync_captures skal logge på INFO niveau."""
    content = read_agent()
    assert 'log.info("Syncing' in content, \
        "FEJL: _sync_captures skal logge på INFO niveau!"

def test_sync_captures_called_at_startup():
    """_sync_captures skal kaldes ved startup — mindst 3 steder."""
    content = read_agent()
    count = content.count("self._sync_captures()")
    assert count >= 3, \
        f"FEJL: _sync_captures skal kaldes minimum 3 steder, fundet {count}!"

def test_config_interval_5_minutes():
    """config_interval skal være 5 minutter i produktion."""
    content = read_agent()
    assert "config_interval = timedelta(minutes=5)" in content, \
        "FEJL: config_interval skal være 5 minutter — ikke 1!"

def test_check_update_exists():
    """_check_update metode skal eksistere."""
    content = read_agent()
    assert "def _check_update" in content, \
        "FEJL: _check_update metode mangler!"

def test_check_update_skips_lab_mode():
    """_check_update skal springe over i LAB mode."""
    content = read_agent()
    assert "LAB mode aktiv" in content or "enabled" in content, \
        "FEJL: _check_update skal tjekke for LAB mode!"

def test_camera_ready_signal_sent():
    """Edge skal sende camera-ready signal til headend i LAB mode."""
    content = read_agent()
    assert "camera-ready" in content, \
        "FEJL: camera-ready signal mangler!"
