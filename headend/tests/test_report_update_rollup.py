"""
Kontrakt-test for POST /api/updates/report — HLTH-008 multi-target rollup.

Kører direkte mod den faktiske `report_update()`-funktion i `headend/main.py`
(ikke en isoleret simulering, som i den tidligere heartbeat-runde) med en
frisk SQLite-database, så testen verificerer den committede kode
(commit 61802951), ikke en model af den.

Kør (fra headend/):
    python3 -m venv /tmp/hvenv
    /tmp/hvenv/bin/pip install fastapi==0.136.1 sqlalchemy==2.0.49 \
        "python-jose[cryptography]==3.5.0" bcrypt==5.0.0 passlib==1.7.4 \
        slowapi==0.1.9 python-multipart==0.0.27 python-dotenv pytest
    /tmp/hvenv/bin/python3 -m pytest tests/test_report_update_rollup.py -v

Bemærk: kræver IKKE en kørende Postgres/live headend — bruger en midlertidig
SQLite-fil og rammer aldrig produktions-DB'en.
"""
import os
import sys
import tempfile
import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

# VIGTIGT: DATABASE_URL skal sættes FØR `database`/`main` importeres første
# gang i denne proces, fordi `database.py` opretter sit SQLAlchemy engine
# ved modul-import-tid (ikke lazily).
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
        # Ryd alle rækker mellem tests, så samme sqlite-fil kan genbruges
        # uden at tests kan påvirke hinanden (fx "global"-scope der ellers
        # ville se devices fra en tidligere test).
        for table in reversed(database.Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


def _make_device(session, device_id, customer_id="cust-1", site_id="site-1"):
    device = database.Device(
        device_id=device_id,
        customer_id=customer_id,
        site_id=site_id,
        app_version="1.0.0",
    )
    session.add(device)
    session.commit()
    return device


def _make_update(session, scope="site", scope_id="site-1", status="approved"):
    update = database.PendingUpdate(
        update_type="app_updates",
        version="1.1.0",
        scope=scope,
        scope_id=scope_id,
        status=status,
    )
    session.add(update)
    session.commit()
    return update


def test_multi_target_site_rollout_waits_for_all_devices(db_session):
    """HLTH-008: global status må ikke flippe til 'deployed' før ALLE targets er det."""
    _make_device(db_session, "dev-1")
    _make_device(db_session, "dev-2")
    _make_device(db_session, "dev-3")
    update = _make_update(db_session, scope="site", scope_id="site-1")

    main.report_update({"update_id": update.id, "status": "deployed", "device_id": "dev-1"}, db=db_session)
    main.report_update({"update_id": update.id, "status": "downloading", "device_id": "dev-2"}, db=db_session)

    db_session.refresh(update)
    assert update.status == "approved", "status skal IKKE flippe før alle targets er terminale"
    assert update.deployed_count == 1

    main.report_update({"update_id": update.id, "status": "deployed", "device_id": "dev-2"}, db=db_session)
    main.report_update({"update_id": update.id, "status": "deployed", "device_id": "dev-3"}, db=db_session)

    db_session.refresh(update)
    assert update.status == "deployed"
    assert update.deployed_count == 3
    assert update.failed_count == 0


def test_single_device_scope_flips_immediately(db_session):
    """scope='device' (ét target) skal fortsat flippe global status øjeblikkeligt."""
    _make_device(db_session, "dev-1")
    update = _make_update(db_session, scope="device", scope_id="dev-1")

    main.report_update({"update_id": update.id, "status": "deployed", "device_id": "dev-1"}, db=db_session)

    db_session.refresh(update)
    assert update.status == "deployed"
    assert update.deployed_count == 1  # var tidligere fastfrosset på 0 (bug, nu rettet)


def test_mixed_outcome_across_targets_is_conservative_rollback(db_session):
    """Blandet udfald (nogle deployed, nogle rolled_back) -> global status 'rolled_back'."""
    _make_device(db_session, "dev-1")
    _make_device(db_session, "dev-2")
    update = _make_update(db_session, scope="global", scope_id=None)

    main.report_update({"update_id": update.id, "status": "deployed", "device_id": "dev-1"}, db=db_session)
    main.report_update({"update_id": update.id, "status": "rolled_back", "device_id": "dev-2"}, db=db_session)

    db_session.refresh(update)
    assert update.status == "rolled_back"
    assert update.deployed_count == 1
    assert update.failed_count == 1


def test_progress_status_never_flips_global_status(db_session):
    """Rene fremskridtsstatusser (queued/downloading/installing) må aldrig flippe global status."""
    _make_device(db_session, "dev-1")
    update = _make_update(db_session, scope="site", scope_id="site-1")

    for status in ("queued", "downloading", "verifying", "backing_up", "installing"):
        main.report_update({"update_id": update.id, "status": status, "device_id": "dev-1"}, db=db_session)
        db_session.refresh(update)
        assert update.status == "approved"
        assert update.deployed_count == 0
        assert update.failed_count == 0
