from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_requirement_import_is_review_gated_and_source_hashed():
    source = (ROOT / "headend/tools/import_grc_requirements.py").read_text()
    assert 'status="candidate_review"' in source
    assert '"source_sha256"' in source
    assert 'relationship="requires_decision_review"' in source
    assert 'parser.add_argument("--apply", action="store_true")' in source
    assert "|PROV|R)" not in source


def test_generated_reports_read_from_grc_database():
    api = (ROOT / "headend/api/grc_register_api.py").read_text()
    ui = (ROOT / "timelapse-ui/src/pages/CompliancePage.tsx").read_text()
    assert '@router.get("/reports/{report_type}")' in api
    assert "Source of truth: PostgreSQL" in api
    assert "GRC rapporter" in ui
    assert "/api/grc/register/reports/${reportPath}" in ui
    assert '@router.get("/reports/standard/{standard}")' in api
    assert "Engineering mapping only" in api


def test_risk_and_adr_import_preserves_source_and_review_state():
    source = (ROOT / "headend/tools/import_grc_risks_decisions.py").read_text()
    assert 'external_id="ADR-001"' in source
    assert 'status="accepted"' in source
    assert '"validate_current_runtime"' in source
    assert "grc_source_permanent" in source
