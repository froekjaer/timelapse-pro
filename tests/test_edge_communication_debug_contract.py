from pathlib import Path


def test_edge_communication_logger_redacts_secrets_and_private_keys():
    source = Path("headend/api/edge_communication_debug_api.py").read_text(encoding="utf-8")
    assert "EdgeApiCommunicationLog" in source
    assert "_SECRET_RE" in source
    assert "private_key" in source
    assert "authorization" in source
    assert "[redacted]" in source
    assert "_redact_query_string(request.url.query)" in source
    assert "BEGIN [A-Z ]*PRIVATE KEY" in source
    assert "request_body_json=json.dumps(parsed_body" in source
    assert "request.headers.get(\"authorization\")" not in source.lower()


def test_edge_communication_debug_tracks_transport_security_and_edge_paths():
    source = Path("headend/api/edge_communication_debug_api.py").read_text(encoding="utf-8")
    assert '"/api/edge/"' in source
    assert '"/api/config/"' in source
    assert '"/api/captures/"' in source
    assert '"/api/updates/report"' in source
    assert "x-forwarded-proto" in source
    assert '"encrypted"' in source
    assert '"unencrypted"' in source
    assert "transport_security" in source


def test_edge_communication_debug_has_excel_export_and_admin_route():
    source = Path("headend/api/edge_communication_debug_api.py").read_text(encoding="utf-8")
    main_source = Path("headend/main.py").read_text(encoding="utf-8")
    migration = Path("headend/migrations/v33_edge_communication_debug.sql").read_text(encoding="utf-8")
    assert '@router.get("/export.xlsx")' in source
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in source
    assert 'require_role("admin")' in source
    assert "register_admin_route_bundle" in main_source
    assert "CREATE TABLE IF NOT EXISTS edge_api_communication_logs" in migration
    assert "request_body_json" in migration
    assert "transport_security" in migration


def test_edge_communication_debug_ui_is_reachable_from_admin_menu():
    app_source = Path("timelapse-ui/src/App.tsx").read_text(encoding="utf-8")
    nav_source = Path("timelapse-ui/src/components/Navbar.tsx").read_text(encoding="utf-8")
    page_source = Path("timelapse-ui/src/pages/EdgeCommunicationsPage.tsx").read_text(encoding="utf-8")
    assert 'path="/edge-communications"' in app_source
    assert "EdgeCommunicationsPage" in app_source
    assert "Edge API" in nav_source
    assert "/api/admin/edge-communications" in page_source
    assert "/api/admin/edge-communications/export.xlsx" in page_source
    assert "Ukrypteret" in page_source
    assert "Rå kommunikationsdata" in page_source


def test_edge_communication_logging_is_gated_behind_a_bounded_capture_session():
    """2026-08-31 (Peter): the always-on logger wrote a DB row for every
    single Edge API call, for every device, forever. Now it must only log
    while an explicit, time- and/or count-bounded capture session is
    active — and an idle Headend must skip body-parsing entirely, not just
    the DB write."""
    source = Path("headend/api/edge_communication_debug_api.py").read_text(encoding="utf-8")
    database_source = Path("headend/database.py").read_text(encoding="utf-8")
    migration = Path("headend/migrations/v34_edge_communication_capture_sessions.sql").read_text(encoding="utf-8")
    page_source = Path("timelapse-ui/src/pages/EdgeCommunicationsPage.tsx").read_text(encoding="utf-8")

    assert "class EdgeCommunicationCaptureSession" in database_source
    assert "duration_minutes" in database_source and "max_packets" in database_source

    assert "_any_capture_session_might_be_active" in source
    assert "_match_active_capture_session" in source
    # The idle-skip must happen BEFORE the request body is read/parsed.
    idle_skip_pos = source.index("_any_capture_session_might_be_active(db)")
    body_read_pos = source.index("await request.body()")
    assert idle_skip_pos < body_read_pos

    assert '@router.post("/capture/start")' in source
    assert '@router.post("/capture/{session_id}/stop")' in source
    assert '@router.get("/capture/status")' in source
    # An unbounded (no duration, no packet limit) session must be rejected.
    assert "duration_minutes is None and max_packets is None" in source

    assert "CREATE TABLE IF NOT EXISTS edge_communication_capture_sessions" in migration

    assert "capture/start" in page_source
    assert "capture/status" in page_source
    assert "Start capture" in page_source
    assert "Stop capture" in page_source


def test_edge_communication_list_can_be_cleared():
    """Peter (2026-08-31): "kan du lave så man kan lave en clear listen med
    datapakker, så man kan starte forfra" — a destructive action, so the UI
    must confirm before calling it."""
    source = Path("headend/api/edge_communication_debug_api.py").read_text(encoding="utf-8")
    page_source = Path("timelapse-ui/src/pages/EdgeCommunicationsPage.tsx").read_text(encoding="utf-8")

    assert '@router.delete("")' in source
    assert "def clear_communications" in source
    assert "q.delete(synchronize_session=False)" in source

    assert "clearList" in page_source
    assert "window.confirm" in page_source
    assert "method: 'DELETE'" in page_source
    assert "Ryd liste" in page_source
