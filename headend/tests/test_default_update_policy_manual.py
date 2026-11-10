from pathlib import Path


def test_consequential_security_updates_require_explicit_approval_by_default():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    block = source.split("def _default_update_policy() -> dict:", 1)[1].split("\ndef ", 1)[0]

    assert '"os_security": "manual"' in block
    assert '"application_security": "manual"' in block
    assert '"timelapse_security": "manual"' in block
    assert 'allow_auto=True' in source
