import main
import redaction_api
import inspect


def test_redaction_router_uses_the_headend_session_secret():
    assert redaction_api.JWT_SECRET == main.JWT_SECRET


def test_redaction_image_lookup_does_not_write_sensitive_tmp_log():
    source = inspect.getsource(redaction_api._find_image_path)

    assert "redaction_debug.log" not in source
