"""Edge-side tests for the commissioning-key disable lifecycle (2026-08-24).

Verify-before-disable, MFA-enrollment style: edge/agent.py reports evidence
of a successful servicetekniker publickey login (feeds Device.
servicetekniker_verified_at server-side, the gate headend/commissioning_key.py
checks before allowing disable), and applies a headend-declared "disabled"
state by removing the shared commissioning key from candidate accounts'
authorized_keys. See Dokumentation/HANDOVER_LOG.md.
"""
from pathlib import Path
from unittest.mock import MagicMock

import agent as edge_agent


def _make_agent():
    return edge_agent.EdgeAgent.__new__(edge_agent.EdgeAgent)


def test_login_evidence_detects_accepted_servicetekniker_publickey(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(
        edge_agent, "subprocess",
        MagicMock(run=MagicMock(return_value=MagicMock(
            returncode=0,
            stdout="Aug 24 19:47:12 host sshd[123]: Accepted publickey for servicetekniker from 10.0.0.1 port 1 ssh2: ED25519 SHA256:abc\n",
        ))),
    )
    assert agent._check_servicetekniker_login_evidence() is True


def test_login_evidence_false_when_no_matching_line(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(
        edge_agent, "subprocess",
        MagicMock(run=MagicMock(return_value=MagicMock(
            returncode=0,
            stdout="Aug 24 19:47:12 host sshd[123]: Accepted publickey for orangepi from ::1 port 1 ssh2: ED25519 SHA256:abc\n",
        ))),
    )
    assert agent._check_servicetekniker_login_evidence() is False


def test_login_evidence_fails_closed_on_journalctl_error(monkeypatch):
    agent = _make_agent()
    monkeypatch.setattr(
        edge_agent, "subprocess",
        MagicMock(run=MagicMock(side_effect=Exception("journalctl unavailable"))),
    )
    assert agent._check_servicetekniker_login_evidence() is False


def test_apply_commissioning_key_disabled_removes_matching_line(tmp_path, monkeypatch):
    agent = _make_agent()
    home = tmp_path / "orangepi" / ".ssh"
    home.mkdir(parents=True)
    authorized_keys = home / "authorized_keys"
    authorized_keys.write_text(
        "ssh-ed25519 AAAAtechnician some-other-comment\n"
        "ssh-ed25519 AAAAheadend timelapse-headend\n"
    )

    def fake_path(spec):
        if spec.startswith("/home/orangepi/"):
            return authorized_keys
        return Path(spec)

    monkeypatch.setattr(edge_agent, "Path", fake_path)
    agent._apply_commissioning_key_disabled(True)

    remaining = authorized_keys.read_text()
    assert "timelapse-headend" not in remaining
    assert "some-other-comment" in remaining


def test_apply_commissioning_key_disabled_noop_when_not_disabled(tmp_path, monkeypatch):
    agent = _make_agent()
    home = tmp_path / "orangepi" / ".ssh"
    home.mkdir(parents=True)
    authorized_keys = home / "authorized_keys"
    original = "ssh-ed25519 AAAAheadend timelapse-headend\n"
    authorized_keys.write_text(original)

    def fake_path(spec):
        return authorized_keys if spec.startswith("/home/orangepi/") else Path(spec)

    monkeypatch.setattr(edge_agent, "Path", fake_path)
    agent._apply_commissioning_key_disabled(False)

    assert authorized_keys.read_text() == original


def test_apply_commissioning_key_disabled_skips_missing_home(tmp_path, monkeypatch):
    agent = _make_agent()
    missing = tmp_path / "does-not-exist" / ".ssh" / "authorized_keys"

    def fake_path(spec):
        return missing if spec.startswith("/home/") else Path(spec)

    monkeypatch.setattr(edge_agent, "Path", fake_path)
    # Must not raise even though none of the candidate paths exist.
    agent._apply_commissioning_key_disabled(True)
