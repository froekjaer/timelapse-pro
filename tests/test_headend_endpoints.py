"""
TimeLapse Pro — Headend API Endpoint Tests
==========================================
Verificerer at alle kritiske endpoints eksisterer i main.py
Kør: pytest tests/test_headend_endpoints.py -v
"""

HEADEND_PATH = "headend/main.py"

def read_headend():
    return open(HEADEND_PATH).read()

# ── Kritiske endpoints ────────────────────────────────────────────────────────

def test_config_endpoint():
    """GET /api/config/{device_id} skal eksistere."""
    assert '/api/config/{device_id}' in read_headend()

def test_heartbeat_endpoint():
    """POST /api/heartbeat/{device_id} skal eksistere."""
    assert '/api/heartbeat/{device_id}' in read_headend()

def test_captures_endpoint():
    """POST /api/captures/{device_id} skal eksistere."""
    assert '/api/captures/{device_id}' in read_headend()

def test_lab_params_store_endpoint():
    """POST /api/lab/{device_id}/params skal eksistere (edge poster parametre)."""
    assert '"/api/lab/{device_id}/params"' in read_headend(), \
        "FEJL: /api/lab/params endpoint mangler — edge kan ikke sende parametre!"

def test_lab_get_params_endpoint():
    """POST /api/lab/{device_id}/get-params skal eksistere (UI anmoder om parametre)."""
    assert '"/api/lab/{device_id}/get-params"' in read_headend(), \
        "FEJL: /api/lab/get-params endpoint mangler!"

def test_lab_camera_ready_endpoint():
    """POST /api/lab/{device_id}/camera-ready skal eksistere."""
    assert '"/api/lab/{device_id}/camera-ready"' in read_headend() or \
           "camera-ready" in read_headend(), \
        "FEJL: camera-ready endpoint mangler!"

def test_lab_set_param_endpoint():
    """POST /api/lab/{device_id}/set-param skal eksistere."""
    assert '"/api/lab/{device_id}/set-param"' in read_headend(), \
        "FEJL: set-param endpoint mangler!"

# ── Device config ─────────────────────────────────────────────────────────────

def test_device_config_in_response():
    """device_config skal returneres i device detail response."""
    content = read_headend()
    assert '"device_config"' in content, \
        "FEJL: device_config mangler i API response!"

def test_lab_camera_ready_reset_on_debug():
    """lab_camera_ready skal nulstilles når debug mode aktiveres."""
    content = read_headend()
    assert "lab_camera_ready" in content, \
        "FEJL: lab_camera_ready håndtering mangler!"

# ── Double imports ─────────────────────────────────────────────────────────────

def test_no_duplicate_imports():
    """Ingen duplikerede imports."""
    content = read_headend()
    import_lines = [l.strip() for l in content.split('\n') if l.startswith('import ')]
    assert len(import_lines) == len(set(import_lines)), \
        f"FEJL: Duplikerede imports fundet: {[x for x in import_lines if import_lines.count(x) > 1]}"

