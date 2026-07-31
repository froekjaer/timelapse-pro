"""Hardcoded-infrastructure-value ratchet (assessment doc 03 recommendation).

Counts hardcoded host/infra values (loopback IPs, macOS volume/homebrew paths,
project domains) in headend/ and edge/ production Python. The baseline may only
SHRINK: new hardcoded values fail CI, and every extraction to DB-settings/UI
lowers the baseline. This operationalises the config rule "everything tunable in
UI + DB; only startup parameters in .env".

To lower the baseline after moving values to settings: update
tests/hardcoded_baseline.json to the new (lower) count in the same commit.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASELINE_FILE = Path(__file__).resolve().parent / "hardcoded_baseline.json"

PATTERN = re.compile(r"127\.0\.0\.1|/Volumes/|/opt/homebrew|froekjaer\.dk|timelapse-pro\.dk")
ROOTS = ("headend", "edge")


def _count():
    total = 0
    per_file = {}
    for root in ROOTS:
        for p in sorted((REPO / root).rglob("*.py")):
            rel = str(p.relative_to(REPO))
            if "/tests/" in rel or p.name.startswith("test_"):
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            n = len(PATTERN.findall(txt))
            if n:
                per_file[rel] = n
                total += n
    return total, per_file


def test_hardcoded_values_do_not_grow():
    baseline = json.loads(BASELINE_FILE.read_text())["max_hardcoded_matches"]
    total, per_file = _count()
    assert total <= baseline, (
        f"Hardcoded infra values grew to {total} (baseline {baseline}). Move new "
        f"values to DB-settings/UI (config rule), or if intentional lower the "
        f"baseline in the same commit.\nPer file:\n"
        + "\n".join(f"  {f}: {n}" for f, n in sorted(per_file.items())))
