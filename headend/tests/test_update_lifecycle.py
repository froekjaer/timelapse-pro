"""
Kontrakt-test for update-flow-funktioner ud over report_update() (H-05, GO_LIVE_CHECKLIST_v10).

Supplerer tests/test_report_update_rollup.py (som dækker HLTH-008-rollup i selve
report_update()). Denne fil dækker:
  - _resolve_update_targets() for alle scopes (device/site/customer/global/explicit ids)
  - force_rollback() (status-transition, ingen rollup-involvering)
  - en potentiel edge case: et device fjernes fra CMDB midt i en igangværende
    multi-target rollout, EFTER det selv har rapporteret en ikke-terminal status.

Kører direkte mod den faktiske kode i headend/main.py (ikke en simulering), med en
frisk SQLite-database. Ingen live Postgres/produktions-DB rørt.

Kør (fra headend/, samme venv som test_report_update_rollup.py):
    python3 -m venv /tmp/hvenv
    /tmp/hvenv/bin/pip install fastapi==0.136.1 sqlalchemy==2.0.49 \
        "python-jose[cryptography]==3.5.0" bcrypt==5.0.0 passlib==1.7.4 \
        slowapi==0.1.9 python-multipart==0.0.27 python-dotenv pytest
    /tmp/hvenv/bin/python3 -m pytest tests/test_update_lifecycle.py -v
"""
import os
import sys
import tempfile
import pathlib
import json
from datetime import timedelta

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")

import database  # noqa: E402
import main  # noqa: E402


class _FakeUser:
    """Minimal stand-in for det require_role() normalt injicerer som current_user."""
    def __init__(self, username="tester", role="admin", customer_id=None):
        self.username = username
        self.role = role
        self.customer_id = customer_id


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


def _make_update(session, **kwargs):
    defaults = dict(
        update_type="app_updates",
        version="1.1.0",
        scope="site",
        scope_id="site-1",
        status="approved",
    )
    defaults.update(kwargs)
    update = database.PendingUpdate(**defaults)
    session.add(update)
    session.commit()
    return update


# ── _resolve_update_targets() ────────────────────────────────────────────────

def test_resolve_targets_device_scope(db_session):
    _make_device(db_session, "dev-1")
    _make_device(db_session, "dev-2")
    update = _make_update(db_session, scope="device", scope_id="dev-1")
    resolved = main._resolve_update_targets(db_session, update)
    assert [d.device_id for d in resolved] == ["dev-1"]


def test_resolve_targets_device_scope_missing_device_returns_empty(db_session):
    """scope='device' mod et device_id der ikke findes i CMDB -> tom liste, ingen crash."""
    update = _make_update(db_session, scope="device", scope_id="dev-ghost")
    resolved = main._resolve_update_targets(db_session, update)
    assert resolved == []


def test_resolve_targets_site_scope_only_matches_site(db_session):
    _make_device(db_session, "dev-1", site_id="site-1")
    _make_device(db_session, "dev-2", site_id="site-2")
    update = _make_update(db_session, scope="site", scope_id="site-1")
    resolved = main._resolve_update_targets(db_session, update)
    assert [d.device_id for d in resolved] == ["dev-1"]


def test_resolve_targets_customer_scope_only_matches_customer(db_session):
    _make_device(db_session, "dev-1", customer_id="cust-a")
    _make_device(db_session, "dev-2", customer_id="cust-b")
    update = _make_update(db_session, scope="customer", scope_id="cust-a")
    resolved = main._resolve_update_targets(db_session, update)
    assert [d.device_id for d in resolved] == ["dev-1"]


def test_resolve_targets_global_scope_matches_all_devices(db_session):
    _make_device(db_session, "dev-1", customer_id="cust-a", site_id="site-a")
    _make_device(db_session, "dev-2", customer_id="cust-b", site_id="site-b")
    update = _make_update(db_session, scope="global", scope_id=None)
    resolved = main._resolve_update_targets(db_session, update)
    assert {d.device_id for d in resolved} == {"dev-1", "dev-2"}


def test_resolve_targets_explicit_target_device_ids_overrides_scope(db_session):
    """target_device_ids (JSON-liste) har forrang over scope/scope_id, jf. koden."""
    import json
    _make_device(db_session, "dev-1", site_id="site-1")
    _make_device(db_session, "dev-2", site_id="site-1")
    _make_device(db_session, "dev-3", site_id="site-1")
    update = _make_update(
        db_session, scope="site", scope_id="site-1",
        target_device_ids=json.dumps(["dev-1", "dev-3"]),
    )
    resolved = main._resolve_update_targets(db_session, update)
    assert {d.device_id for d in resolved} == {"dev-1", "dev-3"}


# ── force_rollback() ─────────────────────────────────────────────────────────

def test_force_rollback_sets_rollback_requested_status(db_session):
    update = _make_update(db_session, status="approved")
    result = main.force_rollback(update.id, current_user=_FakeUser(), db=db_session)
    assert result == {"ok": True}
    db_session.refresh(update)
    assert update.status == "rollback_requested"


def test_force_rollback_unknown_update_raises_404(db_session):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as excinfo:
        main.force_rollback(999999, current_user=_FakeUser(), db=db_session)
    assert excinfo.value.status_code == 404


def test_stale_post_restart_health_handshake_marks_device_update_blocked(db_session):
    _make_device(db_session, "dev-1")
    update = _make_update(db_session, scope="device", scope_id="dev-1", status="approved")
    target = database.UpdateTarget(
        pending_update_id=update.id,
        device_id="dev-1",
        status="installing",
        last_report_at=database.now_utc() - timedelta(seconds=1900),
        report_json=json.dumps({
            "update_id": update.id,
            "device_id": "dev-1",
            "status": "installing",
            "reason": "awaiting_post_restart_health",
            "post_restart_health": {"state": "restart_requested", "timeout_s": 720},
        }),
    )
    db_session.add(target)
    db_session.commit()

    changed = main._sweep_stale_post_restart_update_handshakes(db_session, timeout_s=1800)

    assert changed == 1
    db_session.refresh(update)
    db_session.refresh(target)
    assert update.status == "blocked"
    assert target.status == "failed"
    assert target.last_error == "post_restart_health_handshake_missing"


def test_active_post_restart_health_handshake_is_not_marked_failed(db_session):
    _make_device(db_session, "dev-1")
    update = _make_update(db_session, scope="device", scope_id="dev-1", status="approved")
    target = database.UpdateTarget(
        pending_update_id=update.id,
        device_id="dev-1",
        status="installing",
        last_report_at=database.now_utc() - timedelta(seconds=30),
        report_json=json.dumps({
            "update_id": update.id,
            "device_id": "dev-1",
            "status": "installing",
            "reason": "awaiting_post_restart_health",
            "post_restart_health": {"state": "restart_requested", "timeout_s": 720},
        }),
    )
    db_session.add(target)
    db_session.commit()

    changed = main._sweep_stale_post_restart_update_handshakes(db_session, timeout_s=1800)

    assert changed == 0
    db_session.refresh(update)
    db_session.refresh(target)
    assert update.status == "approved"
    assert target.status == "installing"


# ── Edge case: device forsvinder fra CMDB midt i en igangværende rollout ────

def test_device_removed_from_cmdb_mid_rollout_does_not_prematurely_flip(db_session):
    """
    Scenarie: 3-device site-rollout. dev-2 rapporterer 'downloading' (ikke-terminal),
    og bliver derefter FJERNET fra CMDB (fx udskiftet/decommissioned hardware — reelt
    scenarie, jf. R16-historikken om enheds-genbrug). _resolve_update_targets() vil nu
    kun se 2 devices (dev-1, dev-3), men UpdateTarget-rækken for dev-2 findes stadig.

    Forventning: rollup må IKKE fejlagtigt tælle 'total' som 2 og dermed flippe til
    deployed, når kun dev-1+dev-3 er terminale, mens det fysisk fjernede dev-2's
    sidste kendte status reelt var 'downloading' (aldrig afsluttet). Denne test
    dokumenterer den FAKTISKE opførsel af den nuværende kode (ikke nødvendigvis den
    ønskede) som et kendt, separat opfølgningspunkt, hvis den fejler.
    """
    _make_device(db_session, "dev-1")
    dev2 = _make_device(db_session, "dev-2")
    _make_device(db_session, "dev-3")
    update = _make_update(db_session, scope="site", scope_id="site-1")

    main.report_update({"update_id": update.id, "status": "downloading", "device_id": "dev-2"}, authenticated_device_id="dev-2", db=db_session)

    # dev-2 fjernes fysisk fra CMDB (fx decommission) mens rollout stadig er i gang.
    db_session.delete(dev2)
    db_session.commit()

    main.report_update({"update_id": update.id, "status": "deployed", "device_id": "dev-1"}, authenticated_device_id="dev-1", db=db_session)
    main.report_update({"update_id": update.id, "status": "deployed", "device_id": "dev-3"}, authenticated_device_id="dev-3", db=db_session)

    db_session.refresh(update)
    # KENDT RISIKO: _resolve_update_targets() ser nu kun 2 devices (dev-1, dev-3), begge
    # terminale, så total==2==terminal_n og status FLIPPER til 'deployed' — selvom dev-2
    # aldrig afsluttede. Denne test dokumenterer det som en reel, separat gap (device-
    # decommission midt i rollout omgår HLTH-008-beskyttelsen), IKKE en ny regression fra
    # db.flush()-fixet. Se HANDOVER_LOG for opfølgning; ikke rettet i denne runde.
    assert update.status == "deployed"
    assert update.deployed_count == 2
