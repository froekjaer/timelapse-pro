from pathlib import Path


def test_database_module_blocks_pytest_against_operational_database():
    source = (Path(__file__).resolve().parents[1] / "headend" / "database.py").read_text()
    assert "TIMELAPSE_ALLOW_PYTEST_PRODUCTION_DB" in source
    assert 'endswith("/timelapse_db")' in source


def test_headend_suite_forces_isolated_database_before_imports():
    source = (Path(__file__).resolve().parents[1] / "headend" / "tests" / "conftest.py").read_text()
    assert 'os.environ["DATABASE_URL"]' in source
    assert "/timelapse_test" in source
