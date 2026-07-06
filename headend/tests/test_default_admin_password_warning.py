"""
Kontrakt-test for GO_LIVE_CHECKLIST_v10.md §C-03 ("bekræft super_admin-password er
ændret fra default").

Baggrund (periodisk tjek, 2026-07-06, Claude): `_ensure_super_admin()` logger kun ÉN
gang, ved selve oprettelsen af standard-admin-brugeren ("Standard super_admin
oprettet — SKIFT PASSWORD STRAKS..."). Hvis den log-linje bliver overset (fx fordi
ingen så terminalen i det øjeblik, eller SIEM-retentionen har rullet den ud), er der
intet der siden minder om risikoen — C-03 kan derfor ikke bekræftes løbende, kun ved
selve installationstidspunktet.

Ny funktion `_warn_if_default_admin_password_active()` (main.py, kaldt fra
`_startup_ensure_admin()` ved HVERT opstart, ikke kun ved oprettelse) tjekker om en
aktiv admin/super_admin-konto stadig autentificerer mod standard-passwordet
"changeme", via `_verify_password()` (bcrypt, salt-uafhængig). Hvis ja, logges
`log.critical(...)`, som samles op af `headend/siem.py`s generiske log-baserede
SIEM-pipeline (samme mønster som andre log-drevne sikkerhedshændelser i denne fil) —
dvs. risikoen forbliver synlig i SIEM ved hvert opstart, indtil password rent
faktisk skiftes.

Denne test dækker KUN detektionslogikken (ingen live SIEM/logging-integration testet
her) — kører direkte mod den faktiske `main._warn_if_default_admin_password_active()`
med en midlertidig SQLite-database, samme mønster som
`test_capture_access_log.py`. Ingen live Postgres/headend rørt, ingen live service
genstartet.

Kør (fra headend/):
    python3 -m venv /tmp/hvenv
    /tmp/hvenv/bin/pip install fastapi==0.136.1 sqlalchemy==2.0.49 \
        "python-jose[cryptography]==3.5.0" bcrypt==5.0.0 passlib==1.7.4 \
        slowapi==0.1.9 python-multipart==0.0.27 python-dotenv pytest
    /tmp/hvenv/bin/python3 -m pytest tests/test_default_admin_password_warning.py -v
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


def _make_user(session, username, role, password, *, is_active=True):
    user = database.User(
        username=username,
        email=f"{username}@example.test",
        password_hash=main._hash_password(password),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.commit()
    return user


def test_warns_when_super_admin_has_default_password(db_session, caplog):
    """Aktiv super_admin med password 'changeme' skal udløse log.critical()."""
    _make_user(db_session, "admin", "super_admin", "changeme")

    with caplog.at_level(logging.CRITICAL, logger="headend"):
        main._warn_if_default_admin_password_active(db_session)

    assert any(
        "changeme" in rec.message and "admin" in rec.message
        for rec in caplog.records
        if rec.levelno == logging.CRITICAL
    )


def test_no_warning_when_password_changed(db_session, caplog):
    """Super_admin med et rigtigt password må IKKE udløse nogen advarsel."""
    _make_user(db_session, "admin", "super_admin", "et-helt-andet-sikkert-password")

    with caplog.at_level(logging.CRITICAL, logger="headend"):
        main._warn_if_default_admin_password_active(db_session)

    assert not any(rec.levelno == logging.CRITICAL for rec in caplog.records)


def test_inactive_default_password_account_does_not_warn(db_session, caplog):
    """En DEAKTIVERET konto med standard-password er ikke en aktiv risiko —
    skal ikke give støj i SIEM."""
    _make_user(db_session, "old-admin", "super_admin", "changeme", is_active=False)

    with caplog.at_level(logging.CRITICAL, logger="headend"):
        main._warn_if_default_admin_password_active(db_session)

    assert not any(rec.levelno == logging.CRITICAL for rec in caplog.records)


def test_non_admin_role_with_default_password_does_not_warn(db_session, caplog):
    """Scope er bevidst begrænset til admin/super_admin — en viewer/operator med
    samme password er ikke i scope for DENNE go-live-blokker (C-03 handler
    specifikt om super_admin-adgang)."""
    _make_user(db_session, "viewer1", "viewer", "changeme")

    with caplog.at_level(logging.CRITICAL, logger="headend"):
        main._warn_if_default_admin_password_active(db_session)

    assert not any(rec.levelno == logging.CRITICAL for rec in caplog.records)


def test_warns_for_each_matching_admin_independently(db_session, caplog):
    """To forskellige admin-konti med standard-passwordet skal begge give deres
    egen advarsel (så begge username'r er synlige i SIEM, ikke kun den første)."""
    _make_user(db_session, "admin", "super_admin", "changeme")
    _make_user(db_session, "admin2", "admin", "changeme")

    with caplog.at_level(logging.CRITICAL, logger="headend"):
        main._warn_if_default_admin_password_active(db_session)

    critical_messages = [rec.message for rec in caplog.records if rec.levelno == logging.CRITICAL]
    assert any("admin" in m and "admin2" not in m for m in critical_messages)
    assert any("admin2" in m for m in critical_messages)


def test_malformed_hash_does_not_crash_or_block_other_checks(db_session, caplog):
    """En korrupt/ugyldig password_hash (fx fra en tidligere migrationsfejl) må
    aldrig stoppe opstarten eller skjule en reel advarsel for de øvrige brugere.
    _verify_password() returnerer False (sluger exception) ved ugyldig hash, så
    denne bruger stille springes over — men admin2's reelle advarsel skal stadig
    komme igennem."""
    broken = database.User(
        username="broken",
        email="broken@example.test",
        password_hash="not-a-valid-bcrypt-hash",
        role="super_admin",
        is_active=True,
    )
    db_session.add(broken)
    db_session.commit()
    _make_user(db_session, "admin2", "super_admin", "changeme")

    with caplog.at_level(logging.CRITICAL, logger="headend"):
        main._warn_if_default_admin_password_active(db_session)

    critical_messages = [rec.message for rec in caplog.records if rec.levelno == logging.CRITICAL]
    assert any("admin2" in m for m in critical_messages)
    assert not any("broken" in m for m in critical_messages)
