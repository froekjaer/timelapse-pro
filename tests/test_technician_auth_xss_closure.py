from pathlib import Path

import pytest

from headend.services.technician_auth_security import html_text, validate_technician_device_id


@pytest.mark.parametrize(
    "device_id",
    [
        "TL-C87FF9587CA0",
        "TL-043EB9E72EFD",
        "TL-IMPORT-Kirkbi_A_S-Travbyen-Kamera_1",
        "edge:lab.01",
    ],
)
def test_machine_identifier_allowlist_preserves_known_identifier_shapes(device_id):
    assert validate_technician_device_id(device_id) == device_id


@pytest.mark.parametrize(
    "device_id",
    [
        "",
        " TL-C87FF9587CA0",
        "TL-C87FF9587CA0 ",
        "TL/../../etc/passwd",
        r"TL\\evil",
        "<script>alert(1)</script>",
        'TL-\" onmouseover=\"alert(1)',
        "TL-&lt;script&gt;",
        "TL-\x00BAD",
        "A" * 129,
    ],
)
def test_machine_identifier_rejects_free_form_or_markup(device_id):
    with pytest.raises(ValueError, match="invalid_technician_device_id"):
        validate_technician_device_id(device_id)


def test_html_text_escapes_defense_in_depth():
    payload = '<img src=x onerror="alert(1)">&\''
    escaped = html_text(payload)
    assert "<img" not in escaped
    assert "onerror=\"" not in escaped
    assert escaped == "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&#x27;"


def test_technician_auth_start_validates_before_db_lookup_and_storage():
    source = Path("headend/main.py").read_text(encoding="utf-8")
    block = source.split('def technician_auth_start(', 1)[1].split('@app.post("/api/technician/auth/confirm")', 1)[0]

    validate_i = block.index("validate_technician_device_id(req.device_id)")
    lookup_i = block.index("db.query(Device).filter_by(device_id=device_id)")
    store_i = block.index('"device_id": device_id')
    assert validate_i < lookup_i < store_i
    assert "req.device_id" not in block[lookup_i:]


def test_technician_auth_page_escapes_session_device_id_before_html_render():
    source = Path("headend/main.py").read_text(encoding="utf-8")
    block = source.split('def technician_auth_page(', 1)[1].split('@app.get("/api/auth/me")', 1)[0]

    escape_i = block.index("html_text(session.get(\"device_id\", \"Ukendt\"))")
    render_i = block.index("<strong>Enheds ID:</strong> {safe_device_id}")
    assert escape_i < render_i
    assert "<strong>Enheds ID:</strong> {session.get" not in block
