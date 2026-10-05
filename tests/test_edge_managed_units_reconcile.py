"""lab.60 lesson (2026-10-05): units a release introduces must be installed by
that release. The update runs in the *previous* agent, whose unit list does
not know them — so the new agent installs missing units at startup."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))

import managed_units as mu  # noqa: E402


def _repo(tmp_path):
    scripts = tmp_path / "repo" / "edge" / "scripts"
    scripts.mkdir(parents=True)
    for unit in mu.MANAGED_UNITS:
        (scripts / unit).write_text(f"# {unit}\n")
    (scripts / "timelapse-edge.service").write_text("# edge\n")
    systemd = tmp_path / "systemd"
    systemd.mkdir()
    return tmp_path / "repo", systemd


def test_missing_units_installed_enabled_and_baseline_started(tmp_path):
    repo, systemd = _repo(tmp_path)
    # What Edge1 had after lab.60: only the lab.59 units.
    for unit in mu.MANAGED_UNITS[:8]:
        (systemd / unit).write_text(f"# {unit}\n")
    calls = []
    result = mu.reconcile_managed_units(repo, systemd, calls.append)
    assert result["installed"] == list(mu.MANAGED_UNITS[8:]) and result["updated"] == []
    assert calls[0] == ["systemctl", "daemon-reload"]
    assert ["systemctl", "enable", "timelapse-system-baseline.service"] in calls
    assert ["systemctl", "enable", "timelapse-nightly-reboot.service"] not in calls     # timer-driven
    assert ["systemctl", "restart", "timelapse-system-baseline.service"] in calls
    assert ["systemctl", "restart", "timelapse-nightly-reboot.timer"] in calls
    assert not any("timelapse-edge.service" in c for call in calls for c in call)       # never itself
    assert not (systemd / "timelapse-edge.service").exists()


def test_in_sync_is_a_noop_and_changed_unit_is_updated_without_restarting_technician_services(tmp_path):
    repo, systemd = _repo(tmp_path)
    for unit in mu.MANAGED_UNITS:
        (systemd / unit).write_text(f"# {unit}\n")
    calls = []
    assert mu.reconcile_managed_units(repo, systemd, calls.append) == {"installed": [], "updated": []}
    assert calls == []
    (systemd / "timelapse-totp.service").write_text("# old\n")
    result = mu.reconcile_managed_units(repo, systemd, calls.append)
    assert result["updated"] == ["timelapse-totp.service"]
    assert ["systemctl", "restart", "timelapse-totp.service"] not in calls


def test_agent_reconciles_at_startup_and_edge_unit_mkdir_runs_unsandboxed():
    src = (ROOT / "edge" / "agent.py").read_text(encoding="utf-8")
    assert "self._reconcile_managed_units()" in src
    unit = (ROOT / "edge" / "scripts" / "timelapse-edge.service").read_text(encoding="utf-8")
    assert "ExecStartPre=+/bin/mkdir -p /var/log.hdd/timelapse/breakglass/sessions /var/log/timelapse" in unit
    assert "ProtectSystem=strict" in unit
