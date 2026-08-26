"""2026-08-25: self-heals used to only run once at _startup(), so a
transient failure (useradd hitting a locked /etc/passwd right after an
update install, confirmed live on TL-C87FF9587CA0) stuck until the next
full service restart — which could be days away. Both self-heals are cheap
no-ops once already correct, so _run_sync() now retries them every cycle.
"""
from unittest.mock import MagicMock

import agent as edge_agent


def _make_agent():
    agent = edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)
    agent._device_id = "TL-TESTDEVICE0001"
    agent._running = True
    agent._stop_event = MagicMock(is_set=MagicMock(return_value=False))
    agent._diag = MagicMock(collect=MagicMock(return_value={}))
    agent._db = MagicMock(capture_stats=MagicMock(return_value={}))
    agent._connectivity = MagicMock()
    agent._last_heartbeat = None
    agent._last_inventory = None
    agent._cfg = {}
    agent._pending_siem_cursor = None
    agent._apply_technician_keys = MagicMock()
    agent._check_servicetekniker_login_evidence = MagicMock(return_value=False)
    agent._collect_siem_events_for_sync = MagicMock(return_value=[])
    agent._collect_breakglass_events_for_sync = MagicMock(return_value=[])
    agent._collect_inventory_if_due = MagicMock(return_value=None)
    agent._apply_fetched_config = MagicMock()
    agent._apply_update_policy = MagicMock()
    agent._apply_commissioning_key_disabled = MagicMock()
    agent._apply_break_glass_password = MagicMock(return_value=[])
    agent._sync_time_from_headend = MagicMock()
    agent._reconcile_pending_app_update = MagicMock(return_value=False)
    agent._repair_sshd_authorized_keys_command_missing_u_token = MagicMock()
    agent._repair_emergency_breakglass_account = MagicMock()
    agent._api = MagicMock(sync=MagicMock(return_value=(True, {"pending_updates": []})))
    return agent


def test_run_sync_retries_both_self_heals_every_cycle():
    agent = _make_agent()

    agent._run_sync()

    agent._repair_sshd_authorized_keys_command_missing_u_token.assert_called_once()
    agent._repair_emergency_breakglass_account.assert_called_once()


def test_run_sync_continues_when_a_self_heal_raises():
    agent = _make_agent()
    agent._repair_emergency_breakglass_account = MagicMock(side_effect=Exception("useradd: cannot lock /etc/passwd"))

    agent._run_sync()

    agent._apply_update_policy.assert_called_once()
