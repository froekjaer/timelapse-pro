import importlib.util
from pathlib import Path


PATH = Path(__file__).parents[1] / "headend" / "tools" / "generate_license_compliance_report.py"
SPEC = importlib.util.spec_from_file_location("license_report", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_license_policy_is_fail_closed_for_unknown_and_nonfree() -> None:
    assert MODULE.classify("UNKNOWN")[0] == "unknown"
    assert MODULE.classify("Proprietary")[0] == "blocked"
    assert MODULE.classify("MIT")[0] == "permissive"


def test_copyleft_is_reviewed_not_silently_approved() -> None:
    assert MODULE.classify("GPL-3.0-only")[0] == "review"
    assert MODULE.classify("LGPL-2.1-or-later")[0] == "obligations"


def test_npm_lock_inventory_uses_committed_evidence(tmp_path: Path) -> None:
    lock = tmp_path / "package-lock.json"
    lock.write_text('{"packages":{"":{"name":"app"},"node_modules/example":{"version":"1.2.3","license":"MIT","integrity":"sha512-test"}}}')
    result = MODULE.npm_components(lock)
    assert result[0]["purl"] == "pkg:npm/example@1.2.3"
    assert result[0]["license_evidence"][0]["integrity"] == "sha512-test"
