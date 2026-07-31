"""R09: the restore-drill logic is exercised in CI via its self-test."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "restore_drill", Path(__file__).resolve().parents[1] / "tools" / "restore_drill.py")
restore_drill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(restore_drill)


def test_selftest_passes():
    assert restore_drill.selftest() == 0


def test_guard_refuses_production_target():
    import pytest
    with pytest.raises(restore_drill.DrillRefused):
        restore_drill.guard_target("timelapse_db", "timelapse_db")


def test_guard_refuses_non_allowlisted_target():
    import pytest
    with pytest.raises(restore_drill.DrillRefused):
        restore_drill.guard_target("timelapse_db", "prod_copy")


def test_guard_allows_scratch_target():
    restore_drill.guard_target("timelapse_db", "timelapse_db_restoretest")
