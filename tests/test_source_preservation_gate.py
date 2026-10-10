"""Contract tests for the additive, non-destructive source-preservation gate."""
from pathlib import Path
from tempfile import TemporaryDirectory

from headend.tools.source_preservation_gate import PROTECTED, check


def test_protected_artifacts_have_distinct_paths_and_explicit_owners():
    assert len({item.path for item in PROTECTED}) == len(PROTECTED)
    assert all(item.owner in {"edge", "headend", "ui"} for item in PROTECTED)
    assert all(item.path.startswith("edge/") if item.owner == "edge"
               else item.path.startswith("headend/") if item.owner == "headend"
               else item.path.startswith("timelapse-ui/") for item in PROTECTED)


def test_gate_fails_closed_when_protected_files_missing():
    with TemporaryDirectory() as temp:
        result = check(Path(temp))
    assert result["status"] == "FAIL_SOURCE_PRESENCE"
    assert all(not item["present"] for item in result["artifacts"])


def test_gate_passes_only_with_all_protected_files_present():
    with TemporaryDirectory() as temp:
        root = Path(temp)
        for item in PROTECTED:
            file = root / item.path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("placeholder", encoding="utf-8")
        result = check(root)
    assert result["status"] == "PASS_SOURCE_PRESENCE"
    assert all(item["present"] for item in result["artifacts"])
