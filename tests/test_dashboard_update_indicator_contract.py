"""Dashboard contracts for visible update awareness."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_has_admin_update_indicator():
    source = (ROOT / "timelapse-ui" / "src" / "pages" / "Dashboard.tsx").read_text(encoding="utf-8")

    assert "function UpdateIndicator(" in source
    assert 'api(\'/api/updates/pending\')' in source
    assert "api('/api/updates/pending?status=blocked')" in source
    assert "OS/App security og funktionelle opdateringer er ajour" in source
    assert "ventende opdatering" in source
    assert "<UpdateIndicator updates={pendingUpdates} canConfigure={canConfigure} />" in source
