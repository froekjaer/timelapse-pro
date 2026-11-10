from unittest.mock import MagicMock, patch

import agent as edge_agent


def _agent_with_policy(fresh_policy):
    instance = edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)
    instance._device_id = "TL-TESTDEVICE0001"
    instance._cfg = {"security": {}}
    instance._api = MagicMock()
    instance._api._get.return_value = (True, fresh_policy)
    instance._run_update = MagicMock()
    instance._report_update = MagicMock()
    return instance


def _approved(artifact_id="TL-ART-1"):
    return {
        "id": 42,
        "update_type": "app_updates",
        "status": "approved",
        "artifact": {"artifact_id": artifact_id, "manifest": {"outputs": []}},
    }


def test_stale_inline_policy_cannot_start_update_after_revocation():
    instance = _agent_with_policy({"pending_updates": []})

    instance._apply_update_policy({"pending_updates": [_approved()]})

    instance._api._get.assert_called_once_with("/updates/policy/TL-TESTDEVICE0001")
    instance._run_update.assert_not_called()
    instance._report_update.assert_not_called()


def test_fresh_authorization_must_preserve_exact_artifact_binding():
    instance = _agent_with_policy({"pending_updates": [_approved("TL-ART-2")]})

    instance._apply_update_policy({"pending_updates": [_approved("TL-ART-1")]})

    instance._run_update.assert_not_called()


def test_fresh_matching_authorization_can_reach_execution_gate():
    approved = _approved()
    instance = _agent_with_policy({"pending_updates": [approved]})

    with patch.object(edge_agent, "verify_update_artifact", return_value=(True, "ok")), \
         patch.object(edge_agent, "release_receipt_matches_artifact", return_value=False):
        instance._apply_update_policy({"pending_updates": [approved]})

    instance._run_update.assert_called_once_with(42, "app_updates", approved["artifact"])
