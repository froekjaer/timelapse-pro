import pytest

import main


@pytest.mark.parametrize("environment", ["prod", "production", "staging"])
def test_protected_environments_require_explicit_allowed_origin(environment):
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGIN"):
        main._resolve_allowed_origin(environment, None, "https://fallback.invalid")


def test_lab_environment_keeps_local_development_fallback():
    assert main._resolve_allowed_origin("lab", None, None) == "http://127.0.0.1:5173"


def test_explicit_origin_is_used_in_production():
    assert main._resolve_allowed_origin("prod", "https://timelapse-pro.dk", None) == "https://timelapse-pro.dk"
