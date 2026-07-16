from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_grc_register_schema_has_traceability_and_evidence_tables():
    migration = (ROOT / "headend/migrations/v23_grc_register.sql").read_text()
    for table in ("grc_items", "grc_links", "grc_test_runs", "grc_evidence"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
    assert "REFERENCES grc_items(id)" in migration
    assert "sha256 VARCHAR(64)" in migration


def test_grc_register_api_is_database_backed_and_rbac_protected():
    source = (ROOT / "headend/api/grc_register_api.py").read_text()
    assert 'source_of_truth": "postgresql"' in source
    assert "Depends(_writer)" in source
    assert "GrcTestRun" in source
    assert "GrcEvidence" in source


def test_compliance_ui_exposes_authoritative_register():
    source = (ROOT / "timelapse-ui/src/pages/CompliancePage.tsx").read_text()
    assert "GRC register" in source
    assert "api('/api/grc/register')" in source
    assert "PostgreSQL er single source of truth" in source
