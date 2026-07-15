from unittest.mock import MagicMock

import pytest

import database
import main


class _FailingDB:
    def execute(self, *_args, **_kwargs):
        raise RuntimeError("database unavailable")


def test_backup_settings_database_failure_is_not_reported_as_defaults():
    with pytest.raises(main.HTTPException) as exc:
        main.get_backup_settings(_user=object(), db=_FailingDB())

    assert exc.value.status_code == 500
    assert "kunne ikke hentes" in exc.value.detail.lower()


def test_retention_settings_database_failure_is_not_reported_as_defaults():
    with pytest.raises(main.HTTPException) as exc:
        main.get_retention_settings(_user=object(), db=_FailingDB())

    assert exc.value.status_code == 500
    assert "kunne ikke hentes" in exc.value.detail.lower()


def test_nas_path_session_is_closed_when_query_fails(monkeypatch):
    db = MagicMock()
    db.execute.side_effect = RuntimeError("database unavailable")
    monkeypatch.setattr(database, "SessionLocal", lambda: db)

    assert main._get_nas_path() is None
    db.close.assert_called_once()
