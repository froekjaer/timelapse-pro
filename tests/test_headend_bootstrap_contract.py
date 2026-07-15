from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "deploy" / "install" / "bootstrap_headend_macos.sh"


def test_bootstrap_is_pinned_and_verifies_signed_tag() -> None:
    source = SCRIPT.read_text()
    assert "verify-tag" in source
    assert "expected-commit" in source
    assert "rev-list -n1" in source
    assert "checkout --detach" in source


def test_bootstrap_preserves_existing_software() -> None:
    source = SCRIPT.read_text()
    assert "brew upgrade" not in source
    assert "brew install" not in source
    assert "softwareupdate" not in source
    assert "--dry-run" in source
    for port in ("21", "22", "80", "443"):
        assert port in source


def test_bootstrap_collects_coexistence_evidence() -> None:
    source = SCRIPT.read_text()
    assert "LaunchDaemons" in source
    assert "lsof" in source
    assert "homebrew_inventory" in source
    assert "backend_port_free" in source
