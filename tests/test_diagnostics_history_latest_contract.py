"""Diagnostics charts must show the newest bounded time-series window."""

from pathlib import Path


def test_history_limit_selects_newest_rows_before_chronological_rendering():
    source = (Path(__file__).parents[1] / "headend" / "main.py").read_text()
    block = source.split("def get_diagnostics_history(", 1)[1].split(
        "# ── EXIF statistik", 1
    )[0]

    assert ".order_by(Diagnostic.recorded_at.desc())" in block
    assert ".limit(limit)" in block
    assert "rows.reverse()" in block
    assert block.index(".limit(limit)") < block.index("rows.reverse()")
