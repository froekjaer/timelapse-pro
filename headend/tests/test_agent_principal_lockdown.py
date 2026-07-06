"""
Kontrakt-test for M-05 (AgentPrincipal-håndhævelse — "layer 2" af default-deny-
politikken for agent-adgang til staging/prod).

Baggrund: Codex' oprindelige AgentPrincipal/AgentToken/AgentElevationGrant-forslag
(HANDOVER_LOG.md, 2026-07-05) pegede på at politikken i MILJOE_ARKITEKTUR_RD_STAGING_
PROD_v1.md §5 ("Claude/Codex får ALDRIG adgang til staging/prod") kun var menneskelig
disciplin — intet i koden forhindrede det teknisk. Claudes oprindelige svar (samme
dato) foreslog en 5-trins byggerækkefølge: (1) reel infrastruktur-adskillelse
[nu i høj grad opfyldt af Peters fysiske rd/staging/prod-maskinadskillelse,
2026-07-05/06], (2) env-flag + hård afvisning i middleware/opstartstjek ["layer 2,
ikke layer 1" — DETTE er hvad denne test dækker], (3) det fulde AgentPrincipal/
AgentToken/AgentElevationGrant-skema, (4) audit-udvidelse, (5) CLI.

Ny mekanisme (main.py):
  - `_agent_role_blocked_in_this_environment(role)` — ren logik: True hvis
    role == "agent" OG TIMELAPSE_ENV er staging/prod/production.
  - `login()` — afviser (401, generisk fejlbesked) FØR password-verifikation hvis
    brugeren har role="agent" og miljøet er låst. IKKE dækket af denne testfil (se
    nedenfor hvorfor), men er en tynd, mekanisk anvendelse af samme allerede-testede
    helper-funktion.
  - `get_current_user()` — samme spærre, men for ALLEREDE udstedte cookie/JWT-
    sessions. Dette er det centrale håndhævelsespunkt, fordi ALLE autentificerede
    endpoints går igennem denne ene funktion (BootstrapToken/device-auth er en helt
    separat, ikke-relateret mekanisme og påvirkes ikke).
  - `_log_agent_lockdown_status()` — SIEM-synlig status ved hvert opstart, samme
    mønster som `_warn_if_default_admin_password_active()` (C-03).

Bevidst IKKE testet her: selve `/api/auth/login`-endpointet via et rigtigt HTTP-kald.
Endpointet er dekoreret med `@limiter.limit(...)` (slowapi), som forventer en fuld
ASGI-request/`app.state.limiter`-kontekst — ingen eksisterende test i denne mappe
kalder et rate-limited endpoint direkte, og det ville kræve en TestClient-baseret
opsætning som ikke findes andre steder i denne test-suite endnu. login()'s nye
afvisnings-linjer er en ren, mekanisk anvendelse af `_agent_role_blocked_in_this_
environment()` (allerede fuldt dækket nedenfor) plus et `log.critical()`-kald og et
`raise HTTPException(401, ...)` — samme facit som den eksisterende password-
verifikations-gren. Anbefalet manuel efterprøvning på en rigtig kørende instans
(Peter/Codex, da jeg ikke selv kan starte serveren i denne sandbox):

    # Opret en testbruger med role="agent" (fx via et midlertidigt script eller
    # direkte i DB), sæt TIMELAPSE_ENV=staging eller prod, og kør:
    curl -s -X POST http://127.0.0.1:8000/api/auth/login \\
      -H "Content-Type: application/json" \\
      -d '{"username":"test-agent","password":"<det-rigtige-password>"}'
    # Forventet: HTTP 401 "Forkert brugernavn eller adgangskode" (samme besked som
    # forkert password — ingen rolle-lækage), og en log.critical-linje i
    # headend.log der nævner "M-05" og brugernavnet.

Kør (fra headend/):
    python3 -m venv /tmp/hvenv
    /tmp/hvenv/bin/pip install fastapi==0.136.1 sqlalchemy==2.0.49 \\
        "python-jose[cryptography]==3.5.0" bcrypt==5.0.0 passlib==1.7.4 \\
        slowapi==0.1.9 python-multipart==0.0.27 python-dotenv pytest
    /tmp/hvenv/bin/python3 -m pytest tests/test_agent_principal_lockdown.py -v
"""
import os
import sys
import tempfile
import pathlib
import logging

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")

import database  # noqa: E402
import main  # noqa: E402


@pytest.fixture()
def db_session():
    database.create_tables()
    session = database.SessionLocal()
    try:
        yield session
    finally:
        for table in reversed(database.Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


class _FakeRequest:
    """Minimal stand-in for fastapi.Request — kun `.cookies` bruges af
    get_current_user()."""
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


def _make_user(session, username, role, *, is_active=True):
    user = database.User(
        username=username,
        email=f"{username}@example.test",
        password_hash=main._hash_password("irrelevant-i-denne-test"),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.commit()
    return user


# ── _agent_role_blocked_in_this_environment() — ren logik ──────────────────────

@pytest.mark.parametrize("env", ["prod", "production", "staging"])
def test_agent_role_blocked_in_locked_environments(monkeypatch, env):
    monkeypatch.setattr(main, "TIMELAPSE_ENV", env)
    assert main._agent_role_blocked_in_this_environment("agent") is True


@pytest.mark.parametrize("env", ["rd", "lab", "dev", "development", ""])
def test_agent_role_not_blocked_outside_locked_environments(monkeypatch, env):
    monkeypatch.setattr(main, "TIMELAPSE_ENV", env)
    assert main._agent_role_blocked_in_this_environment("agent") is False


@pytest.mark.parametrize("role", ["viewer", "operator", "admin", "super_admin", None, ""])
def test_non_agent_roles_never_blocked_regardless_of_environment(monkeypatch, role):
    monkeypatch.setattr(main, "TIMELAPSE_ENV", "prod")
    assert main._agent_role_blocked_in_this_environment(role) is False


def test_agent_role_check_is_case_and_whitespace_insensitive(monkeypatch):
    """En rolle-streng med afvigende case/whitespace (fx fra en manuel DB-rettelse
    eller en fremtidig UI-formularfejl) må ikke ved en fejl omgå spærren."""
    monkeypatch.setattr(main, "TIMELAPSE_ENV", "prod")
    assert main._agent_role_blocked_in_this_environment(" Agent ") is True
    assert main._agent_role_blocked_in_this_environment("AGENT") is True


# ── get_current_user() — det centrale håndhævelsespunkt for alle sessions ──────

def test_get_current_user_rejects_agent_session_in_prod(monkeypatch, db_session):
    """Kernescenariet: en session der allerede eksisterer (token udstedt FØR
    miljøet blev låst, eller en gendannet DB-kopi) skal stadig blive afvist —
    ikke kun nye login-forsøg."""
    _make_user(db_session, "svc-claude", "agent")
    token = main._create_token({"sub": "svc-claude"})
    fake_request = _FakeRequest(cookies={main.COOKIE_NAME: token})

    monkeypatch.setattr(main, "TIMELAPSE_ENV", "prod")
    result = main.get_current_user(fake_request, db_session)

    assert result is None


def test_get_current_user_allows_agent_session_in_rd(monkeypatch, db_session):
    """Samme bruger, samme session — men i rd (ikke låst) skal den almindelige
    get_current_user()-adfærd gælde uændret (brugeren returneres, evt. begrænsede
    rettigheder håndteres separat af _ROLE_HIERARCHY/require_role, ikke her)."""
    _make_user(db_session, "svc-claude", "agent")
    token = main._create_token({"sub": "svc-claude"})
    fake_request = _FakeRequest(cookies={main.COOKIE_NAME: token})

    monkeypatch.setattr(main, "TIMELAPSE_ENV", "rd")
    result = main.get_current_user(fake_request, db_session)

    assert result is not None
    assert result.username == "svc-claude"


def test_get_current_user_unaffected_for_human_roles_in_prod(monkeypatch, db_session):
    """Spærren må under ingen omstændigheder ramme almindelige menneskelige
    brugere — kun role='agent'."""
    _make_user(db_session, "peter", "super_admin")
    token = main._create_token({"sub": "peter"})
    fake_request = _FakeRequest(cookies={main.COOKIE_NAME: token})

    monkeypatch.setattr(main, "TIMELAPSE_ENV", "prod")
    result = main.get_current_user(fake_request, db_session)

    assert result is not None
    assert result.username == "peter"


def test_get_current_user_rejection_is_logged_critical(monkeypatch, db_session, caplog):
    """Afvisningen skal være synlig i SIEM (log.critical), ikke kun en stille
    None-retur — samme princip som C-03-advarslen."""
    _make_user(db_session, "svc-codex", "agent")
    token = main._create_token({"sub": "svc-codex"})
    fake_request = _FakeRequest(cookies={main.COOKIE_NAME: token})

    monkeypatch.setattr(main, "TIMELAPSE_ENV", "staging")
    with caplog.at_level(logging.CRITICAL, logger="headend"):
        main.get_current_user(fake_request, db_session)

    assert any(
        "M-05" in rec.message and "svc-codex" in rec.message
        for rec in caplog.records
        if rec.levelno == logging.CRITICAL
    )


def test_get_current_user_inactive_agent_still_returns_none_as_before(monkeypatch, db_session):
    """Regressions-værn: en deaktiveret bruger (is_active=False) blev allerede
    afvist FØR denne ændring (findes ikke i query'et) — det må stadig være
    tilfældet, uanset rolle eller miljø."""
    _make_user(db_session, "old-agent", "agent", is_active=False)
    token = main._create_token({"sub": "old-agent"})
    fake_request = _FakeRequest(cookies={main.COOKIE_NAME: token})

    monkeypatch.setattr(main, "TIMELAPSE_ENV", "rd")
    result = main.get_current_user(fake_request, db_session)

    assert result is None


# ── _log_agent_lockdown_status() — opstartssynlighed i SIEM ─────────────────────

@pytest.mark.parametrize("env", ["prod", "production", "staging"])
def test_startup_logs_critical_when_lockdown_active(monkeypatch, caplog, env):
    monkeypatch.setattr(main, "TIMELAPSE_ENV", env)
    with caplog.at_level(logging.CRITICAL, logger="headend"):
        main._log_agent_lockdown_status()

    assert any(
        "M-05" in rec.message and "AKTIV" in rec.message
        for rec in caplog.records
        if rec.levelno == logging.CRITICAL
    )


def test_startup_logs_info_only_when_not_locked(monkeypatch, caplog):
    monkeypatch.setattr(main, "TIMELAPSE_ENV", "rd")
    with caplog.at_level(logging.DEBUG, logger="headend"):
        main._log_agent_lockdown_status()

    assert not any(rec.levelno == logging.CRITICAL for rec in caplog.records)
    assert any("M-05" in rec.message for rec in caplog.records)
