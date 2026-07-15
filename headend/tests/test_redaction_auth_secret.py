import redaction_api
import inspect
from types import SimpleNamespace

import main


def test_redaction_router_delegates_to_central_headend_auth(monkeypatch):
    expected = SimpleNamespace(username="viewer")
    monkeypatch.setattr(main, "get_current_user", lambda request, db: expected)

    assert redaction_api.get_required_user(SimpleNamespace(), db=object()) is expected


def test_redaction_router_has_no_private_jwt_implementation():
    source = inspect.getsource(redaction_api)

    assert "JWT_SECRET" not in source
    assert "jwt.decode" not in source


def test_redaction_image_lookup_does_not_write_sensitive_tmp_log():
    source = inspect.getsource(redaction_api._find_image_path)

    assert "redaction_debug.log" not in source
