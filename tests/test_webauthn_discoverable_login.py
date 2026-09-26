"""login-begin sends an empty allowCredentials by default (added 2026-09-27).
Safari 27 / macOS 27 hung on passkey login with an explicit list containing
transport-less credentials while Chrome and a private Safari window worked.
See Dokumentation/HANDOVER_LOG.md, 2026-09-27 entry.
"""
from pathlib import Path

from headend.services.webauthn_origin import login_allow_credentials

ROOT = Path(__file__).resolve().parents[1]


def test_default_is_discoverable_empty_list():
    assert login_allow_credentials(["a", "b"], None) == []
    assert login_allow_credentials(["a", "b"], "") == []
    assert login_allow_credentials(["a", "b"], "discoverable") == []


def test_list_mode_restores_explicit_descriptors():
    assert login_allow_credentials(["a", "b"], "list") == ["a", "b"]
    assert login_allow_credentials(["a"], " LIST ") == ["a"]


def test_login_begin_still_requires_rp_bound_credentials_and_uses_setting():
    main = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    begin = main.split("def webauthn_login_begin", 1)[1].split("@app.", 1)[0]
    # still 404 when the user has no credential for this RP
    assert "if not allow_creds:" in begin
    assert '_get_setting(db, "webauthn_login_allow_credentials", "discoverable")' in begin


def test_login_complete_still_binds_credential_to_user():
    main = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    complete = main.split("def webauthn_login_complete", 1)[1].split("@app.", 1)[0]
    assert "user_id=user.id, credential_id=credential_id" in complete
    assert "expected_rp_id      = rp_id" in complete
