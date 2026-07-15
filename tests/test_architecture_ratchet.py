"""Architecture ratchets adopted from the 2026-07-15 architecture review."""

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((Path(__file__).with_name("architecture_baseline.json")).read_text(encoding="utf-8"))
MAIN = ROOT / "headend" / "main.py"
DIRECT_ROUTE = re.compile(r"^@(app|_legacy_app)\.(get|post|put|patch|delete)\(", re.MULTILINE)


def test_headend_main_does_not_grow_beyond_baseline():
    line_count = len(MAIN.read_text(encoding="utf-8").splitlines())

    assert line_count <= BASELINE["headend_main_max_lines"], (
        f"headend/main.py grew to {line_count} lines. New functionality must use "
        "an APIRouter/domain module; lower the baseline after extraction."
    )


def test_no_new_direct_routes_are_added_to_headend_main():
    source = MAIN.read_text(encoding="utf-8")
    route_count = len(DIRECT_ROUTE.findall(source))

    assert route_count <= BASELINE["headend_main_max_direct_routes"], (
        f"headend/main.py now contains {route_count} direct routes. Add new endpoints "
        "through an authenticated APIRouter and lower the baseline after extraction."
    )
