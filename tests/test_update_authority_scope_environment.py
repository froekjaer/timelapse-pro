from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
HEADEND = ROOT / "headend"
if str(HEADEND) not in sys.path:
    sys.path.insert(0, str(HEADEND))

from services.update_authority import update_applies_to_device


def obj(**kwargs):
    return SimpleNamespace(**kwargs)


def test_customer_and_site_scopes_reach_matching_device():
    device = obj(device_id="TL-1", customer_id="C-1", site_id="S-1", environment="production")
    inv = obj(device_id="TL-1", environment="production")
    assert update_applies_to_device(obj(scope="customer", scope_id="C-1", environment="production", target_device_ids=None), device, inv)
    assert update_applies_to_device(obj(scope="site", scope_id="S-1", environment="production", target_device_ids=None), device, inv)


def test_scope_mismatch_fails_closed():
    device = obj(device_id="TL-1", customer_id="C-1", site_id="S-1", environment="production")
    inv = obj(device_id="TL-1", environment="production")
    assert not update_applies_to_device(obj(scope="customer", scope_id="C-2", environment="production", target_device_ids=None), device, inv)
    assert not update_applies_to_device(obj(scope="site", scope_id="S-2", environment="production", target_device_ids=None), device, inv)


def test_environment_isolation_blocks_test_update_from_production():
    device = obj(device_id="TL-1", customer_id="C-1", site_id="S-1", environment="production")
    inv = obj(device_id="TL-1", environment="production")
    update = obj(scope="global", scope_id=None, environment="test", target_device_ids=None)
    assert not update_applies_to_device(update, device, inv)


def test_lab_rd_dev_aliases_are_test_environment():
    update = obj(scope="global", scope_id=None, environment="test", target_device_ids=None)
    for env in ("lab", "test", "rd", "dev", "development"):
        assert update_applies_to_device(update, obj(device_id="TL-1", environment=env), obj(device_id="TL-1", environment=env))


def test_unknown_device_environment_fails_closed():
    update = obj(scope="device", scope_id="TL-1", environment="production", target_device_ids=None)
    assert not update_applies_to_device(update, obj(device_id="TL-1"), obj(device_id="TL-1", environment=None))


def test_explicit_target_list_never_bypasses_environment():
    update = obj(scope="global", scope_id=None, environment="test", target_device_ids='["TL-1"]')
    prod = obj(device_id="TL-1", environment="production")
    assert not update_applies_to_device(update, prod, prod)
    test = obj(device_id="TL-1", environment="test")
    assert update_applies_to_device(update, test, test)


def test_main_policy_and_report_use_same_canonical_predicate():
    source = (ROOT / "headend" / "main.py").read_text(encoding="utf-8")
    assert "from services.update_authority import update_applies_to_device as _update_applies_to_device" in source
    policy_start = source.index('def get_update_policy(')
    report_start = source.index('def report_update(')
    policy_block = source[policy_start:report_start]
    report_block = source[report_start:source.index('def report_available_updates(', report_start)]
    assert "if not _update_applies_to_device(u, device, inventory):" in policy_block
    assert "if not _update_applies_to_device(u, report_device, report_inventory):" in report_block
    assert 'or_(_PU.scope == "global", _PU.scope_id == device_id)' not in policy_block
