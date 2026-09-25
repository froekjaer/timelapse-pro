"""WebAuthn credentials are bound to the RP ID they were registered under
(added 2026-09-25). login-begin previously offered every credential for the
user on both backend.timelapse-pro.dk and timelapse.froekjaer.dk, although a
passkey only works for its own RP ID; Safari 27 then hung without showing the
Touch ID sheet. See Dokumentation/HANDOVER_LOG.md, 2026-09-25 entry.
"""
from types import SimpleNamespace
from pathlib import Path

from webauthn.helpers.structs import AuthenticatorTransport

from headend.services.webauthn_origin import credential_descriptors

ROOT = Path(__file__).resolve().parents[1]


def _cred(cid: bytes, rp_id, transports=None):
    return SimpleNamespace(credential_id=cid, rp_id=rp_id, transports=transports)


def test_only_matching_and_legacy_credentials_are_offered():
    creds = [
        _cred(b"pro", "timelapse-pro.dk", '["internal", "hybrid"]'),
        _cred(b"legacy", None),
        _cred(b"froekjaer", "timelapse.froekjaer.dk"),
    ]
    ids = [d.id for d in credential_descriptors(creds, "timelapse-pro.dk")]
    assert ids == [b"pro", b"legacy"]


def test_descriptor_keeps_stored_transports():
    (d,) = credential_descriptors([_cred(b"x", "timelapse-pro.dk", '["internal"]')], "timelapse-pro.dk")
    assert d.transports == [AuthenticatorTransport.INTERNAL]


def test_no_credentials_for_rp_yields_empty_list():
    assert credential_descriptors([_cred(b"f", "timelapse.froekjaer.dk")], "timelapse-pro.dk") == []


def test_main_stores_and_backfills_rp_id():
    main = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    register_complete = main.split("def webauthn_register_complete", 1)[1].split("@app.", 1)[0]
    login_complete = main.split("def webauthn_login_complete", 1)[1].split("@app.", 1)[0]
    assert "rp_id         = rp_id," in register_complete
    assert "cred.rp_id = cred.rp_id or rp_id" in login_complete
    migration = (ROOT / "headend/migrations/v39_webauthn_credential_rp_id.sql").read_text(encoding="utf-8")
    # Existing rows must be backfilled, otherwise NULL rows keep being offered
    # to both RPs and the fix only helps after a login that already works.
    assert "SET rp_id = 'timelapse.froekjaer.dk'" in migration
    assert "SET rp_id = 'timelapse-pro.dk'" in migration


def test_login_page_never_waits_forever_on_the_authenticator():
    login_page = (ROOT / "timelapse-ui/src/pages/LoginPage.tsx").read_text(encoding="utf-8")
    handler = login_page.split("async function handleWebAuthn()", 1)[1]
    assert "WebAuthnAbortService.cancelCeremony()" in handler
    # the deadline covers login-begin and login-complete, not only the authenticator
    assert handler.count("withDeadline(fetch(") == 2
    assert "withDeadline(startAuthentication(" in handler
    # no background login-begin: it would overwrite a challenge in use elsewhere
    assert "prefetch" not in login_page.lower()
    assert "clearTimeout(timer)" in handler
    assert "setLoading(false)" in handler
