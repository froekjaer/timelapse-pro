"""Kimi F-006: SFTP must never auto-trust a server host key."""

from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "edge" / "upload" / "sftp.py").read_text(encoding="utf-8")


def test_autoaddpolicy_is_not_present():
    assert "AutoAddPolicy" not in SOURCE
    assert "TIMELAPSE_SFTP_ALLOW_AUTO_ADD_HOSTKEY" not in SOURCE


def test_missing_known_hosts_fails_closed():
    assert "if not known_hosts.is_file():" in SOURCE
    assert "automatic host-key trust is forbidden" in SOURCE


def test_reject_policy_is_always_configured_before_connect():
    reject_pos = SOURCE.index("paramiko.RejectPolicy()")
    connect_pos = SOURCE.index("self._ssh.connect(**connect_kwargs)")
    assert reject_pos < connect_pos
