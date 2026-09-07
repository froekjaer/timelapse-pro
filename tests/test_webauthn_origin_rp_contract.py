from types import SimpleNamespace


def _request(origin: str):
    return SimpleNamespace(headers={"origin": origin}, url=SimpleNamespace(scheme="https", netloc="ignored"))


def test_webauthn_primary_timelapse_pro_origin_uses_parent_rp(monkeypatch):
    from headend import main

    values = {
        "base_url": "https://timelapse.froekjaer.dk",
        "webauthn_allowed_origins": "https://backend.timelapse-pro.dk:8443,https://timelapse.froekjaer.dk",
        "webauthn_rp_name": "TimeLapse Pro",
    }
    monkeypatch.setattr(main, "_get_setting", lambda _db, key, default="": values.get(key, default))

    rp_id, rp_name, origin = main._webauthn_settings(None, _request("https://backend.timelapse-pro.dk:8443"))

    assert rp_id == "timelapse-pro.dk"
    assert rp_name == "TimeLapse Pro"
    assert origin == "https://backend.timelapse-pro.dk:8443"


def test_webauthn_legacy_froekjaer_origin_keeps_own_rp(monkeypatch):
    from headend import main

    values = {
        "base_url": "https://timelapse.froekjaer.dk",
        "webauthn_allowed_origins": "https://backend.timelapse-pro.dk:8443,https://timelapse.froekjaer.dk",
    }
    monkeypatch.setattr(main, "_get_setting", lambda _db, key, default="": values.get(key, default))

    rp_id, _rp_name, origin = main._webauthn_settings(None, _request("https://timelapse.froekjaer.dk"))

    assert rp_id == "timelapse.froekjaer.dk"
    assert origin == "https://timelapse.froekjaer.dk"


def test_webauthn_unlisted_origin_fails_closed(monkeypatch):
    import pytest
    from fastapi import HTTPException
    from headend import main

    monkeypatch.setattr(
        main,
        "_get_setting",
        lambda _db, key, default="": {
            "webauthn_allowed_origins": "https://backend.timelapse-pro.dk:8443,https://timelapse.froekjaer.dk",
        }.get(key, default),
    )

    with pytest.raises(HTTPException) as exc:
        main._webauthn_settings(None, _request("https://timelapsepro.dk"))

    assert exc.value.status_code == 400
