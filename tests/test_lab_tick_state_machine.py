"""Hardware-free regression tests for the Edge LAB state machine."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import agent as edge_agent


def _make_agent(cfg_data: dict):
    agent = edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)
    agent._device_id = "TL-TEST-EDGE"
    agent._cfg = {"config_version": cfg_data.get("config_version", "v1")}
    agent._api = MagicMock()
    agent._api.fetch_config.return_value = (True, cfg_data)
    agent._api._post.return_value = (True, {})
    agent._api.clear_lab_params.return_value = (True, {})
    agent._api.clear_lab_command.return_value = (True, {})
    agent._cfg_mgr = MagicMock()
    agent._cfg_mgr.load.return_value = cfg_data
    agent._uploader = MagicMock()
    agent._driver = MagicMock()
    agent._relay = SimpleNamespace(camera=MagicMock(), modem=MagicMock())
    agent._live_frame_enabled = False
    agent._lab_relay_on = False
    agent._check_and_apply_updates_if_due = MagicMock()
    agent._camera_power_mode = MagicMock(return_value="relay")
    agent._camera_power_on = MagicMock()
    agent._camera_power_off = MagicMock()
    agent._camera_warmup_seconds = MagicMock(return_value=0)
    agent._build_camera_commands = MagicMock(return_value=[])
    agent._apply_config_changes = MagicMock()
    agent._check_config_version = MagicMock()
    agent._lab_stop_frame_push = MagicMock()
    agent._lab_start_frame_push = MagicMock()
    return agent


def _enabled_config(**extra):
    return {
        "config_version": "v1",
        "debug_mode": {"enabled": True},
        "pending_params": [],
        "lab_command": {},
        **extra,
    }


def test_lab_tick_retries_then_powercycles_before_success(monkeypatch):
    agent = _make_agent(_enabled_config())
    agent._driver.connect.side_effect = [RuntimeError("busy"), RuntimeError("busy"), None]
    monkeypatch.setattr(edge_agent.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(edge_agent, "_FRAME_PUSH_AVAILABLE", False)

    agent._lab_tick({"config_poll_s": 0})

    assert agent._driver.connect.call_count == 3
    agent._camera_power_off.assert_called_once_with("camera connect failure", force=True)
    assert agent._camera_power_on.call_count == 2
    assert agent._lab_relay_on is True
    assert agent._lab_cam_connect_failures == 0
    agent._api._post.assert_any_call("/lab/TL-TEST-EDGE/camera-ready", {"ready": True})


def test_lab_tick_exhausted_retries_remains_not_ready(monkeypatch):
    agent = _make_agent(_enabled_config())
    agent._driver.connect.side_effect = RuntimeError("camera unavailable")
    monkeypatch.setattr(edge_agent.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(edge_agent, "_FRAME_PUSH_AVAILABLE", False)

    agent._lab_tick({"config_poll_s": 0})

    assert agent._driver.connect.call_count == 3
    assert agent._lab_cam_connect_failures == 3
    assert agent._lab_relay_on is False
    assert not any(call.args[0].endswith("/camera-ready") for call in agent._api._post.call_args_list)


def test_lab_tick_disabled_stops_camera_and_persists_config(monkeypatch):
    cfg = _enabled_config(debug_mode={"enabled": False})
    agent = _make_agent(cfg)
    agent._lab_relay_on = True
    monkeypatch.setattr(edge_agent.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(edge_agent, "_FRAME_PUSH_AVAILABLE", False)

    agent._lab_tick({"config_poll_s": 0})

    agent._driver.disconnect.assert_called_once()
    agent._camera_power_off.assert_called_once_with("lab disabled", force=True)
    agent._cfg_mgr.save_config.assert_called_once_with(cfg)
    agent._uploader.update_config.assert_called_once_with(cfg)
    assert agent._lab_relay_on is False


def test_lab_tick_set_param_serialises_camera_access_and_reports_result(monkeypatch):
    command = {"type": "set_param", "command_id": "cmd-1", "key": "iso", "value": "200"}
    agent = _make_agent(_enabled_config(lab_command=command))
    agent._lab_relay_on = True
    agent._driver.get_config_param.return_value = {"key": "iso", "value": "200"}
    agent._driver.get_all_config.return_value = [{"key": "iso", "value": "200"}]
    agent._driver.get_profile_summary.return_value = {"model": "Nikon Z30"}
    monkeypatch.setattr(edge_agent.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(edge_agent, "_FRAME_PUSH_AVAILABLE", False)

    agent._lab_tick({"config_poll_s": 0})

    agent._lab_stop_frame_push.assert_called_once()
    agent._driver.set_config.assert_called_once_with("iso", "200")
    agent._lab_start_frame_push.assert_called_once()
    result_calls = [call for call in agent._api._post.call_args_list if call.args[0].endswith("/result")]
    assert len(result_calls) == 1
    assert result_calls[0].args[1]["ok"] is True
    assert result_calls[0].args[1]["command_id"] == "cmd-1"
    agent._api.clear_lab_command.assert_called_once_with("TL-TEST-EDGE")
