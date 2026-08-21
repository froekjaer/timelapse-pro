"""Regression tests for automatic BT-TOTP secret sync (SEC-016-BOOTSTRAP-GAP).

edge/agent.py already fetches merged config (incl. bt_totp) on every
heartbeat through a device-token-authenticated endpoint. This closes the
bootstrap deadlock where a device with no factory secret could never sync
a real one, since the old sync path required already being logged in
locally. See Dokumentation/SEC-016_Factory_BT_TOTP_Bootstrap_Gap.md.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import agent as edge_agent


def _make_agent():
    agent = edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)
    return agent


def test_sync_writes_new_secret_and_restarts_totp_service(tmp_path, monkeypatch):
    config_path = tmp_path / "bt-config.yaml"
    monkeypatch.setattr(edge_agent.EdgeAgent, "BT_TOTP_CONFIG_PATH", config_path)
    agent = _make_agent()

    with patch.object(edge_agent.subprocess, "run") as run_mock:
        agent._sync_bt_totp_config({"secret": "REALSECRET123", "sid": "camera-abc"})

    written = edge_agent.yaml.safe_load(config_path.read_text())
    assert written["totp"] == {"secret": "REALSECRET123", "sid": "camera-abc"}
    run_mock.assert_called_once_with(
        ["systemctl", "restart", "timelapse-totp.service"], check=False
    )


def test_sync_is_a_noop_when_headend_has_no_secret_yet(tmp_path, monkeypatch):
    config_path = tmp_path / "bt-config.yaml"
    config_path.write_text("totp:\n  secret: FACTORYSECRET\n  sid: factory-default\n")
    monkeypatch.setattr(edge_agent.EdgeAgent, "BT_TOTP_CONFIG_PATH", config_path)
    agent = _make_agent()

    with patch.object(edge_agent.subprocess, "run") as run_mock:
        agent._sync_bt_totp_config({"secret": "", "sid": "unprovisioned"})

    # Factory secret must survive untouched — never overwritten with nothing.
    written = edge_agent.yaml.safe_load(config_path.read_text())
    assert written["totp"]["secret"] == "FACTORYSECRET"
    run_mock.assert_not_called()


def test_sync_is_idempotent_when_already_up_to_date(tmp_path, monkeypatch):
    config_path = tmp_path / "bt-config.yaml"
    config_path.write_text("totp:\n  secret: REALSECRET123\n  sid: camera-abc\n")
    monkeypatch.setattr(edge_agent.EdgeAgent, "BT_TOTP_CONFIG_PATH", config_path)
    agent = _make_agent()

    with patch.object(edge_agent.subprocess, "run") as run_mock:
        agent._sync_bt_totp_config({"secret": "REALSECRET123", "sid": "camera-abc"})

    run_mock.assert_not_called()


def test_sync_preserves_other_management_settings_in_the_file(tmp_path, monkeypatch):
    config_path = tmp_path / "bt-config.yaml"
    config_path.write_text(
        "management:\n  https_port: 8443\n  enable_interactive_shell: false\n"
        "totp:\n  secret: ''\n  sid: unprovisioned\n"
    )
    monkeypatch.setattr(edge_agent.EdgeAgent, "BT_TOTP_CONFIG_PATH", config_path)
    agent = _make_agent()

    with patch.object(edge_agent.subprocess, "run"):
        agent._sync_bt_totp_config({"secret": "REALSECRET123", "sid": "camera-abc"})

    written = edge_agent.yaml.safe_load(config_path.read_text())
    assert written["management"] == {"https_port": 8443, "enable_interactive_shell": False}
    assert written["totp"] == {"secret": "REALSECRET123", "sid": "camera-abc"}


def test_sync_creates_file_atomically_with_root_only_permissions(tmp_path, monkeypatch):
    config_path = tmp_path / "sub" / "bt-config.yaml"
    monkeypatch.setattr(edge_agent.EdgeAgent, "BT_TOTP_CONFIG_PATH", config_path)
    agent = _make_agent()

    with patch.object(edge_agent.subprocess, "run"):
        agent._sync_bt_totp_config({"secret": "REALSECRET123", "sid": "camera-abc"})

    assert config_path.exists()
    mode = oct(config_path.stat().st_mode)[-3:]
    assert mode == "600"
    # No stray temp file left behind.
    assert list(config_path.parent.glob(".*.tmp")) == []


def _make_agent_for_apply_fetched_config(cached_version: str):
    agent = _make_agent()
    agent._cfg = {"config_version": cached_version}
    agent._api = MagicMock()
    agent._api.ensure_signing_enrolled.return_value = (True, None)
    agent._cfg_mgr = MagicMock()
    agent._cfg_mgr.load.return_value = {"config_version": cached_version}
    agent._uploader = MagicMock()
    return agent


def test_apply_fetched_config_syncs_bt_totp_even_when_version_unchanged():
    """Regression for the actual production bug (2026-08-21): a device whose
    locally cached config_version already equals Headend's current hash
    would never get another chance to sync BT-TOTP, because the sync call
    used to live inside _apply_config_changes(), which only runs on a
    version diff. sync_bt_totp_config() is cheap/idempotent by design, so it
    must run on every fetched config regardless of whether the version
    changed — otherwise a device can be stuck on a stale secret forever
    even though Headend has always been serving the correct one."""
    agent = _make_agent_for_apply_fetched_config("same-hash")
    agent._sync_bt_totp_config = MagicMock()

    agent._apply_fetched_config({
        "config_version": "same-hash",  # identical to cached — no "real" change
        "bt_totp": {"secret": "X", "sid": "camera-1"},
    })

    agent._sync_bt_totp_config.assert_called_once_with({"secret": "X", "sid": "camera-1"})


def test_apply_fetched_config_still_syncs_bt_totp_when_version_changed():
    agent = _make_agent_for_apply_fetched_config("old-hash")
    agent._sync_bt_totp_config = MagicMock()

    agent._apply_fetched_config({
        "config_version": "new-hash",
        "bt_totp": {"secret": "X", "sid": "camera-1"},
    })

    agent._sync_bt_totp_config.assert_called_once_with({"secret": "X", "sid": "camera-1"})


def test_apply_fetched_config_survives_bt_totp_sync_exception():
    agent = _make_agent_for_apply_fetched_config("same-hash")
    agent._sync_bt_totp_config = MagicMock(side_effect=RuntimeError("disk full"))

    # Must not raise — a sync failure shouldn't take down config apply.
    agent._apply_fetched_config({
        "config_version": "same-hash",
        "bt_totp": {"secret": "X", "sid": "camera-1"},
    })
