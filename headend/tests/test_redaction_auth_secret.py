import redaction_api
import inspect
from types import SimpleNamespace


def test_redaction_router_delegates_to_central_headend_auth(monkeypatch):
    """redaction_api imports get_current_user from auth.py at module scope
    (2026-08-26) — patch the name where redaction_api actually looks it up,
    not main's (which is a separate binding of the same original function,
    unaffected by patching main's copy)."""
    expected = SimpleNamespace(username="viewer")
    monkeypatch.setattr(redaction_api, "get_current_user", lambda request, db: expected)

    assert redaction_api.get_required_user(SimpleNamespace(), db=object()) is expected


def test_redaction_router_has_no_private_jwt_implementation():
    source = inspect.getsource(redaction_api)

    assert "JWT_SECRET" not in source
    assert "jwt.decode" not in source


def test_redaction_image_lookup_does_not_write_sensitive_tmp_log():
    source = inspect.getsource(redaction_api._find_image_path)

    assert "redaction_debug.log" not in source


def test_redaction_image_lookup_supports_canonical_customer_site_camera_tree(tmp_path):
    image = tmp_path / "Frøkjær" / "Nordre_Villavej_17c" / "Kamera_1" / "2026" / "09" / "01" / "capture_20260901_195005.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"fake-jpeg")
    capture = SimpleNamespace(
        device_id="TL-C87FF9587CA0",
        filename="capture_20260901_195005.jpg",
    )

    assert redaction_api._find_image_path(capture, base_path=str(tmp_path)) == image


def test_redaction_image_lookup_ignores_thumbnail_copy(tmp_path):
    thumb = tmp_path / "Frøkjær" / "Nordre_Villavej_17c" / "Kamera_1" / "2026" / "09" / "01" / ".thumbs" / "capture_20260901_195005.jpg"
    thumb.parent.mkdir(parents=True)
    thumb.write_bytes(b"thumbnail")
    capture = SimpleNamespace(
        device_id="TL-C87FF9587CA0",
        filename="capture_20260901_195005.jpg",
    )

    try:
        redaction_api._find_image_path(capture, base_path=str(tmp_path))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("thumbnail copy must not be used as redaction source")
