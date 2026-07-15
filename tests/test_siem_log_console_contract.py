from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_siem_events_support_server_side_source_filter() -> None:
    source = (ROOT / "headend" / "siem.py").read_text()
    start = source.index("def get_events(")
    section = source[start:start + 1800]
    assert "source:" in section
    assert "SecurityEvent.source" in section


def test_drift_exposes_normalized_log_sources_not_raw_files() -> None:
    source = (ROOT / "timelapse-ui" / "src" / "pages" / "DriftPage.tsx").read_text()
    assert "Logs &amp; hændelser" in source
    assert "/siem?source=edge_journal" in source
    assert "/siem?source=nginx-timelapse-error.log" in source
