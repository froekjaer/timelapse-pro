from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "headend" / "main.py").read_text()


def test_login_uses_user_level_mfa_resolver():
    login_start = MAIN.index("def login(")
    login_end = MAIN.index("\n@app.", login_start)
    login = MAIN[login_start:login_end]
    assert "mfa_required = _mfa_required_for_user(db, user)" in login
    assert "mfa_required = _mfa_required_for_role(policy, user.role)" not in login


def test_session_responses_honor_user_exemption():
    assert MAIN.count('"mfa_required_effective": _mfa_required_for_user(db, current_user)') >= 2


def test_user_resolver_checks_exemptions_before_role_default():
    start = MAIN.index("def _mfa_required_for_user(")
    end = MAIN.index("\n\ndef ", start)
    resolver = MAIN[start:end]
    assert resolver.index("mfa_exempt_usernames") < resolver.index("_mfa_required_for_role")
