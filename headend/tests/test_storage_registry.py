from pathlib import Path
from types import SimpleNamespace

from storage_registry import binding_status


def test_binding_status_accepts_writable_directory(tmp_path: Path):
    row = SimpleNamespace(id=1, logical_name="captures-primary", backend_type="local",
                          path=str(tmp_path), access_mode="read_write", priority=10,
                          active=True, expected_volume_uuid=None, description=None)
    status = binding_status(row)
    assert status["healthy"] is True
    assert status["readable"] is True
    assert status["writable"] is True
    assert status["free_bytes"] > 0


def test_binding_status_rejects_missing_directory(tmp_path: Path):
    row = SimpleNamespace(id=2, logical_name="backups-primary", backend_type="local",
                          path=str(tmp_path / "missing"), access_mode="read_write", priority=10,
                          active=True, expected_volume_uuid=None, description=None)
    assert binding_status(row)["healthy"] is False
