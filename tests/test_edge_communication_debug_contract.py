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
