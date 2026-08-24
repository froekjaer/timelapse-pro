"""Regression contract for update promotion target scope."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_production_promotion_does_not_inherit_test_canary_target_ids():
    source = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    block = source[source.index("def promote_update("):source.index("def get_update_policy(")]

    assert "target_environment == \"staging\"" in block
    assert "target_device_ids = u.target_device_ids if target_environment == \"staging\" else None" in block
    assert "Production must re-resolve against its full scope" in block
