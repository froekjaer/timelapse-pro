"""_sync_edge_os_updates() must never supersede an active os_security/os_updates
PendingUpdate based on Edge's own self-reported apt-upgradable count.

Edge is offline by design (only talks to Headend + SFTP). Its own
"apt-get -s --just-print upgrade" (edge/utils/inventory.py
_apt_updates_available()) can only ever reflect its own local, frozen apt
index — it has no way to learn about new upstream Ubuntu security advisories
on its own. Before this fix, every real ticket Headend's own scheduled
catalog scan found (the side with actual internet access) got killed by
Edge's next routine CMDB sync reporting "0 upgradable", before a human could
ever approve it. Found 2026-09-09 chasing why update #290 (Edge 2, 24 real
jammy security packages) kept evaporating within minutes of being created.
"""
import cmdb as cmdb_module
from database import Base, DeviceInventory, PendingUpdate, SessionLocal, engine

DEVICE_ID = "TL-TESTDEVICE-OS-SUPERSEDE"


def _clean(session):
    session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID).delete()
    session.query(DeviceInventory).filter_by(device_id=DEVICE_ID).delete()
    session.commit()


def test_edge_reporting_zero_updates_does_not_supersede_an_active_os_security_ticket():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(DeviceInventory(device_id=DEVICE_ID, environment="production", os_name="Ubuntu 22.04.5 LTS"))
        session.add(PendingUpdate(
            update_type="os_security",
            status="blocked",
            scope="device",
            scope_id=DEVICE_ID,
            version="24 pakker",
            description="24 sikkerhedsopdatering(er) klar via Headend lab-katalog",
        ))
        session.commit()
        inv = session.query(DeviceInventory).filter_by(device_id=DEVICE_ID).first()

        cmdb_module._sync_edge_os_updates(
            session, DEVICE_ID, inv,
            {"os_updates_available": {"total": 0, "security": 0, "packages": []}},
        )
        session.commit()

        ticket = session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID, update_type="os_security").first()
        assert ticket is not None
        assert ticket.status == "blocked", "Edge's stale self-report must not supersede Headend's own real catalog finding"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_edge_reporting_nonzero_updates_still_creates_its_own_observation_ticket():
    # The total>0 branch (Edge's own "CMDB observation — ikke deployable"
    # ticket) is untouched by this fix and must keep working.
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(DeviceInventory(device_id=DEVICE_ID, environment="production", os_name="Ubuntu 22.04.5 LTS"))
        session.commit()
        inv = session.query(DeviceInventory).filter_by(device_id=DEVICE_ID).first()

        cmdb_module._sync_edge_os_updates(
            session, DEVICE_ID, inv,
            {"os_updates_available": {
                "total": 1, "security": 1,
                "packages": [{"name": "libssl3", "old_ver": "3.0.13-4", "new_ver": "3.0.13-5", "source_repo": "jammy-security"}],
            }},
        )
        session.commit()

        ticket = session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID, update_type="os_security").first()
        assert ticket is not None
        assert ticket.status == "blocked"
        assert "CMDB observation" in ticket.description
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()
