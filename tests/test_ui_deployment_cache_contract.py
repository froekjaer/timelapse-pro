"""Contracts preventing a green deploy from serving stale administration UI."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ui_asset_names_include_the_release_identity():
    config = (ROOT / "timelapse-ui/vite.config.ts").read_text(encoding="utf-8")
    assert "process.env.GITHUB_SHA" in config
    assert "entryFileNames: `assets/[name]-[hash]-${buildId}.js`" in config


def test_nginx_templates_revalidate_ui_documents_and_assets():
    for relative in ("deploy/nginx/timelapse.froekjaer.dk.conf", "deploy/install/install_headend.sh"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert 'Cache-Control \\"no-cache, must-revalidate\\"' in source or 'Cache-Control "no-cache, must-revalidate"' in source
        assert "location ^~ /assets/" in source


def test_update_approval_is_visible_and_flow_status_stays_at_the_top():
    source = (ROOT / "timelapse-ui/src/pages/UpdatesPage.tsx").read_text(encoding="utf-8")
    assert 'role="dialog" aria-modal="true"' in source
    assert "Aktivt opdateringsflow" in source
    assert "sticky top-3" in source
    assert "target.status !== 'pending'" in source
    assert "recentlyApproved" in source
