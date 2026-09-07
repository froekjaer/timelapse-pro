"""
_package_level_updates_for_device() — the fix for Peter's 2026-09-07 finding
that CMDB showed everything as "current version" even with hundreds of known-
outdated packages. Root cause: os_security/os_updates/dependency_updates/
dependency_security bundle many packages into one PendingUpdate row with an
aggregate "N pakker" version string; the old per-component table could only
parse a "name version -> version" string (Homebrew's per-package format), so
batch rows were silently invisible. package_details (JSON, added same day)
carries the actual per-package list; this function flattens it — plus
Homebrew's already-per-package data — into one canonical list.
"""
import json

import cmdb as cmdb_module
from database import Base, PendingUpdate, SessionLocal, engine


DEVICE_ID = "TL-TESTDEVICE-PKGLEVEL"


def _clean(session):
    session.query(PendingUpdate).filter_by(scope_id=DEVICE_ID).delete()
    session.commit()


def test_includes_homebrew_per_package_updates():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        software_inventory = {
            "available_software_updates": [
                {"name": "nginx", "installed_version": "1.24.0", "available_version": "1.26.0", "manager": "brew", "kind": "security"},
            ]
        }
        items = cmdb_module._package_level_updates_for_device(session, DEVICE_ID, software_inventory)
        assert len(items) == 1
        assert items[0]["name"] == "nginx"
        assert items[0]["severity"] == "security"
        assert items[0]["source"] == "brew"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_flattens_batch_style_package_details_from_pending_update():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(PendingUpdate(
            update_type="os_security", status="blocked", scope="device", scope_id=DEVICE_ID,
            version="2 pakker",
            package_details=json.dumps([
                {"name": "libssl3", "installed_version": "3.0.13-4", "available_version": "3.0.13-5", "source_repo": "noble-security"},
                {"name": "curl", "installed_version": "8.5.0", "available_version": "8.6.0", "source_repo": "noble-security"},
            ]),
        ))
        session.commit()

        items = cmdb_module._package_level_updates_for_device(session, DEVICE_ID, {})
        assert len(items) == 2
        names = {i["name"] for i in items}
        assert names == {"libssl3", "curl"}
        assert all(i["severity"] == "security" for i in items)
        assert all(i["update_type"] == "os_security" for i in items)
        assert all(i["status"] == "blocked" for i in items)
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_dependency_updates_are_not_marked_security():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(PendingUpdate(
            update_type="dependency_updates", status="blocked", scope="device", scope_id=DEVICE_ID,
            version="1 pakker",
            package_details=json.dumps([
                {"name": "requests", "installed_version": "2.28.0", "available_version": "2.31.0", "source_repo": "pypi"},
            ]),
        ))
        session.commit()

        items = cmdb_module._package_level_updates_for_device(session, DEVICE_ID, {})
        assert len(items) == 1
        assert items[0]["severity"] == "feature"
        assert items[0]["source"] == "pypi"
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_ignores_updates_without_package_details():
    """Historical rows predating this field (or the Homebrew track, which never
    sets it) must not raise — they're simply absent from the per-package list."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(PendingUpdate(
            update_type="os_security", status="blocked", scope="device", scope_id=DEVICE_ID,
            version="3 pakker", package_details=None,
        ))
        session.commit()
        assert cmdb_module._package_level_updates_for_device(session, DEVICE_ID, {}) == []
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()


def test_ignores_non_active_status():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    _clean(session)
    try:
        session.add(PendingUpdate(
            update_type="os_security", status="superseded", scope="device", scope_id=DEVICE_ID,
            version="1 pakker",
            package_details=json.dumps([{"name": "stale-pkg", "installed_version": "1.0", "available_version": "2.0", "source_repo": "x"}]),
        ))
        session.commit()
        assert cmdb_module._package_level_updates_for_device(session, DEVICE_ID, {}) == []
    finally:
        cleanup = SessionLocal()
        _clean(cleanup)
        cleanup.close()
