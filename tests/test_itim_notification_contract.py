from pathlib import Path


ROOT = Path(__file__).parents[1]
ITIM = (ROOT / "headend" / "itim.py").read_text()


def test_itim_notifies_on_firing_and_recovery() -> None:
    section = ITIM[ITIM.index("def evaluate_alerts"):ITIM.index("# ── Rollup")]
    assert "_notify_alert(db, rule, t, ev)" in section
    assert "_notify_alert(db, rule, t, open_ev, resolved=True)" in section
    assert '"resolved" if resolved else "firing"' in section
    assert "ITIM {'LØST' if resolved else 'ALARM'}" in section
