"""Regression test for C-07 (MASTER_REVIEW_CLOSURE_2026-08-15.md): POST
/api/admin/backup/edge-complete/{device_id} took `filename` straight from the
request body and used it, unsanitized, in os.path.join() for both the
SFTP-incoming source path AND the backup-destination path — a filename like
"../../../../etc/passwd" could move an arbitrary file into or out of the
intended backup directory. Same vulnerability class as C-01
(headend/services/path_security.py). Fixed by reusing the existing
_sanitize_filename() helper (basename-only, allowlists chars) — the same one
its sibling endpoint upload_edge_backup already used. _sanitize_filename()
neutralizes traversal by taking os.path.basename() first (so "../x" becomes
just "x"), it does not reject a traversal-shaped input outright.
"""
from unittest.mock import MagicMock

import pytest

import main
from database import Base, Device, SessionLocal, engine

DEVICE_ID = "TL-TESTDEVICE-C07"


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    session.query(Device).filter_by(device_id=DEVICE_ID).delete()
    session.commit()
    session.add(Device(device_id=DEVICE_ID, device_config="{}"))
    session.commit()
    try:
        yield session
    finally:
        session.query(Device).filter_by(device_id=DEVICE_ID).delete()
        session.commit()
        session.close()


@pytest.fixture(autouse=True)
def _writable_backup_dest(monkeypatch, tmp_path):
    # Production falls back to a hardcoded Linux path (/home/peter/backup) if no
    # NAS is configured — not writable in a local/CI sandbox. Point it at a real
    # tmp dir so the test exercises the actual path-join/move logic.
    monkeypatch.setattr(main, "_get_nas_path", lambda: str(tmp_path))
    return tmp_path


def test_traversal_filename_is_neutralized_to_its_basename(db_session, _writable_backup_dest):
    result = main.edge_backup_complete(
        DEVICE_ID,
        {"filename": "../../../../etc/passwd", "size_kb": 1},
        _user=MagicMock(username="operator"),
        db=db_session,
    )
    assert result["status"] == "ok"
    # No source file exists in the test sandbox, so the move is skipped and
    # `path` stays the (still sanitized) SFTP-incoming path — what matters here
    # is that the traversal never survives into the resolved path.
    assert result["path"].endswith("/passwd")
    assert ".." not in result["path"]


def test_normal_filename_is_still_accepted(db_session, _writable_backup_dest):
    result = main.edge_backup_complete(
        DEVICE_ID,
        {"filename": "TL-TESTDEVICE-C07-backup-2026-08-20.tar.gz", "size_kb": 42},
        _user=MagicMock(username="operator"),
        db=db_session,
    )
    assert result["status"] == "ok"
    device = db_session.query(Device).filter_by(device_id=DEVICE_ID).first()
    import json
    stored = json.loads(device.device_config)
    assert stored["backup_complete"]["filename"] == "TL-TESTDEVICE-C07-backup-2026-08-20.tar.gz"


def test_empty_filename_is_rejected(db_session, _writable_backup_dest):
    with pytest.raises(Exception) as exc_info:
        main.edge_backup_complete(
            DEVICE_ID,
            {"filename": "", "size_kb": 1},
            _user=MagicMock(username="operator"),
            db=db_session,
        )
    assert getattr(exc_info.value, "status_code", None) == 400
