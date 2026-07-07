from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = REPO_ROOT / "headend" / "main.py"


@pytest.mark.smoke
def test_backup_and_resilience_endpoints_are_present() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")
    assert '@app.post("/api/admin/backup/trigger")' in source
    assert '@app.get("/api/admin/backup/status")' in source
    assert '@app.get("/api/admin/backup/settings")' in source
    assert '@app.get("/api/admin/resilience/assessment")' in source
    assert '@app.post("/api/admin/backup/trigger-edge/{device_id}")' in source


@pytest.mark.smoke
def test_backup_helpers_exist() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")
    assert 'def _run_backup_archive(' in source
    assert 'def _get_nas_path()' in source
    assert 'def _get_backup_include_images()' in source
    assert 'def _path_status(' in source
