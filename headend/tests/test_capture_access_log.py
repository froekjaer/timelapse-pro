"""
Kontrakt-test for GDPR-adgangslog pr. billede (GO_LIVE_CHECKLIST_v10.md §G-05:
"Download/adgangslog pr. billede implementeret").

Baggrund (periodisk tjek, 2026-07-05, Claude): §G-05 stod som "🟠 Anbefalet" —
ingen kode fandtes til at logge HVEM der har set/downloadet et givent billede,
selvom `DPIA_SKABELON_OG_RETENTION_POLICY_v1.md` §2.4 forudsætter en sådan
audit-evne for at kunne svare på GDPR-indsigtsanmodninger. Ny tabel
`CaptureAccessLog` (database.py) + hjælpefunktion `_log_capture_access()`
(main.py), kaldt fra `GET /api/images/{device_id}/{filename}` EFTER
`_ensure_capture_file_access()` (dvs. kun ved faktisk tilladt adgang).
Bevidst IKKE koblet på thumbnail-endpointet (grid-browsing ville give alt for
stor log-volumen for et rent visnings-formål) — kun selve fuldopløsnings-
billedet, som er det reelle "download/se dette specifikke billede"-øjeblik.

Kører direkte mod den faktiske `main.get_image()` og `main._log_capture_access()`
med en midlertidig SQLite-database og en midlertidig billedfil på disk — ingen
live Postgres/headend rørt.

Kør (fra headend/):
    python3 -m venv /tmp/hvenv
    /tmp/hvenv/bin/pip install fastapi==0.136.1 sqlalchemy==2.0.49 \
        "python-jose[cryptography]==3.5.0" bcrypt==5.0.0 passlib==1.7.4 \
        slowapi==0.1.9 python-multipart==0.0.27 python-dotenv pytest
    /tmp/hvenv/bin/python3 -m pytest tests/test_capture_access_log.py -v
"""
import os
import sys
import tempfile
import pathlib

import pytest
from fastapi import HTTPException

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


def _make_user(session, username="viewer1", role="viewer", customer_id="cust-a"):
    user = database.User(
        username=username,
        email=f"{username}@example.test",
        password_hash="x",
        role=role,
        customer_id=customer_id,
    )
    session.add(user)
    session.commit()
    return user


def _make_device(session, device_id="dev-1", customer_id="cust-a"):
    device = database.Device(
        device_id=device_id,
        customer_id=customer_id,
    )
    session.add(device)
    session.commit()
    return device


def _make_capture(session, device_id="dev-1", filename="img.jpg", customer_id="cust-a"):
    capture = database.Capture(
        device_id=device_id,
        filename=filename,
        customer_id=customer_id,
    )
    session.add(capture)
    session.commit()
    return capture


def test_log_capture_access_writes_expected_fields(db_session):
    """_log_capture_access() skal skrive én CaptureAccessLog-række med
    capture/bruger-identitet og en UTC-timestamp."""
    user = _make_user(db_session)
    capture = _make_capture(db_session)

    main._log_capture_access(db_session, user, capture, action="download")

    rows = db_session.query(database.CaptureAccessLog).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.capture_id == capture.id
    assert row.device_id == "dev-1"
    assert row.filename == "img.jpg"
    assert row.action == "download"
    assert row.user_id == user.id
    assert row.username == "viewer1"
    assert row.role == "viewer"
    assert row.customer_id == "cust-a"
    assert row.accessed_at is not None


def test_log_capture_access_failure_does_not_raise(db_session, monkeypatch):
    """En logging-fejl må ALDRIG forhindre en autoriseret billedvisning —
    _log_capture_access() skal sluge fejlen og rulle sessionen tilbage."""
    user = _make_user(db_session)
    capture = _make_capture(db_session)

    def _boom(*a, **kw):
        raise RuntimeError("simuleret DB-fejl")

    monkeypatch.setattr(db_session, "commit", _boom)

    # Må ikke kaste en exception videre til kalderen (billedvisningen).
    main._log_capture_access(db_session, user, capture, action="download")


def test_get_image_logs_access_on_authorized_view(db_session, monkeypatch, tmp_path):
    """End-to-end: GET /api/images/{device}/{filename} skal, ved autoriseret
    adgang, både returnere billedet OG skrive én adgangslog-række."""
    user = _make_user(db_session)
    _make_device(db_session)
    capture = _make_capture(db_session)

    fake_image = tmp_path / "img.jpg"
    fake_image.write_bytes(b"\xff\xd8\xff\xd9")  # minimal JPEG-lignende bytes

    monkeypatch.setattr(main, "_find_image", lambda device_id, filename: fake_image)

    response = main.get_image(device_id="dev-1", filename="img.jpg", _user=user, db=db_session)

    assert response is not None
    assert str(fake_image) in str(response.path)

    rows = db_session.query(database.CaptureAccessLog).all()
    assert len(rows) == 1
    assert rows[0].capture_id == capture.id
    assert rows[0].username == "viewer1"


def test_get_image_forbidden_access_does_not_log(db_session, monkeypatch, tmp_path):
    """Et 403 (forkert tenant) skal IKKE efterlade en adgangslog-række —
    kun faktisk tilladt adgang må logges."""
    _make_user(db_session, username="viewer_other", customer_id="cust-b")
    other_user = db_session.query(database.User).filter_by(username="viewer_other").first()
    _make_device(db_session, customer_id="cust-a")  # device tilhører cust-a
    _make_capture(db_session, customer_id="cust-a")  # tilhører cust-a, ikke cust-b

    fake_image = tmp_path / "img.jpg"
    fake_image.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(main, "_find_image", lambda device_id, filename: fake_image)

    with pytest.raises(HTTPException) as exc_info:
        main.get_image(device_id="dev-1", filename="img.jpg", _user=other_user, db=db_session)

    assert exc_info.value.status_code == 403
    assert db_session.query(database.CaptureAccessLog).count() == 0
