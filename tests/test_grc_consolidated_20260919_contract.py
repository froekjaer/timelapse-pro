from pathlib import Path
ROOT=Path(__file__).parents[1]
def test_reviewed_requirement_baseline_is_reviewed_and_read_back_guarded():
 s=(ROOT/"headend/tools/import_grc_reviewed_requirements_20260919.py").read_text()
 assert 'SOURCE_URI="artifact://TimeLapse_Pro_Komplet_Krav_og_Gap_Register_2026-09-19.docx"' in s
 assert '"decision_state":"reviewed"' in s
 assert 'relationship="superseded_by_reviewed_requirement"' in s
 assert 'Exact normalized text match' in s
 assert 'len(got)!=len(ROWS) or active!=len(ROWS)' in s
def test_consolidated_report_reads_requirements_findings_and_risks_from_grc():
 s=(ROOT/"headend/tools/export_grc_consolidated_report.py").read_text()
 assert 'filter_by(item_type="requirement")' in s
 assert 'GrcItem.item_type.in_(["finding","risk"])' in s
 assert 'Foto — Functional' in s and 'System — Nonfunctional' in s
 assert 'compliance-bevis' in s
