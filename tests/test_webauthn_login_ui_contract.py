from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_webauthn_login_updates_authoritative_auth_context():
    auth_context = _source("timelapse-ui/src/context/AuthContext.tsx")
    login_page = _source("timelapse-ui/src/pages/LoginPage.tsx")

    assert "acceptSessionUser: (user: User) => void" in auth_context
    assert "function acceptSessionUser(user: User)" in auth_context
    assert "setUser(user)" in auth_context
    assert "acceptSessionUser" in login_page
    assert "acceptSessionUser(u)" in login_page


def test_webauthn_login_does_not_force_full_page_reload_after_success():
    login_page = _source("timelapse-ui/src/pages/LoginPage.tsx")
    webauthn_handler = login_page.split("async function handleWebAuthn()", 1)[1]

    assert "window.location.href = from" not in webauthn_handler
    assert "navigate(from, { replace: true })" in webauthn_handler
