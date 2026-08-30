import json
import stat
from pathlib import Path

from edge.update_lifecycle import (
    cleanup_pending_app_update,
    guard_pending_app_update,
    load_pending_app_update,
    mark_pending_app_update_health_confirmed,
    pending_app_update_matches,
    pending_app_update_path,
    record_pending_app_update_health_probe,
    write_pending_app_update,
    write_post_restart_guard,
)


def _artifact(artifact_id="TL-ART-NEW", commit="new123", version="2.0", outputs=None):
    return {
        "artifact_id": artifact_id,
        "source_commit": commit,
        "version": version,
        "manifest": {"outputs": outputs or [{"path": "edge/agent.py"}]},
    }


def _make_recovery_root(tmp_path: Path, update_id: int = 7) -> Path:
    root = tmp_path / "timelapse_update_recovery"
    recovery = root / f"app-{update_id}-TL-ART-NEW"
    recovery.mkdir(parents=True)
    return recovery


def test_pending_marker_is_exact_durable_and_cleanup_is_scoped(tmp_path: Path):
    repo = tmp_path / "timelapse"
    (repo / "edge").mkdir(parents=True)
    pending = pending_app_update_path(repo)
    recovery = _make_recovery_root(tmp_path)

    write_pending_app_update(
        pending,
        update_id=7,
        artifact=_artifact(),
        recovery_dir=recovery,
        managed_unit_files=("timelapse-edge.service",),
        health_timeout_s=90,
        repo=repo,
    )

    assert pending_app_update_matches(pending, 7, _artifact()) is True
    assert pending_app_update_matches(pending, 8, _artifact()) is False
    assert pending_app_update_matches(pending, 7, _artifact(commit="other")) is False
    assert pending_app_update_matches(pending, 7, _artifact(version="9.9")) is False
    assert stat.S_IMODE(pending.stat().st_mode) == 0o600

    confirmed = mark_pending_app_update_health_confirmed(pending)
    assert confirmed["state"] == "health_confirmed"
    assert load_pending_app_update(pending)["health_confirmed_at"]

    cleanup_pending_app_update(pending)
    assert not pending.exists()
    assert not recovery.exists()


def test_guard_timeout_restores_previous_release_units_and_removes_new_outputs(tmp_path: Path):
    repo = tmp_path / "timelapse"
    prev = repo / "prev"
    edge = repo / "edge"
    (prev / "edge").mkdir(parents=True)
    edge.mkdir(parents=True)

    previous_receipt = {
        "schema": "timelapse.edge.release.v1",
        "artifact_id": "TL-ART-PREV",
        "source_commit": "prev123",
        "version": "1.0",
    }
    (prev / "edge" / "agent.py").write_text("old-agent")
    (prev / "edge" / ".timelapse-release.json").write_text(json.dumps(previous_receipt))
    (edge / "agent.py").write_text("new-agent")
    (edge / "new_feature.py").write_text("candidate-only")
    (edge / ".timelapse-release.json").write_text(json.dumps({
        "schema": "timelapse.edge.release.v1",
        "artifact_id": "TL-ART-NEW",
        "source_commit": "new123",
        "version": "2.0",
    }))

    recovery = _make_recovery_root(tmp_path)
    unit_backup = recovery / "systemd-backup"
    unit_backup.mkdir()
    (unit_backup / "timelapse-edge.service").write_text("old-unit")
    (unit_backup / "timelapse-totp.service").write_text("old-totp-unit")

    systemd_dir = tmp_path / "systemd"
    systemd_dir.mkdir()
    (systemd_dir / "timelapse-edge.service").write_text("new-unit")
    (systemd_dir / "timelapse-totp.service").write_text("new-totp-unit")
    (systemd_dir / "timelapse-new.service").write_text("candidate-new-unit")

    artifact = _artifact(outputs=[
        {"path": "edge/agent.py"},
        {"path": "edge/new_feature.py"},
    ])
    pending = pending_app_update_path(repo)
    write_pending_app_update(
        pending,
        update_id=7,
        artifact=artifact,
        recovery_dir=recovery,
        managed_unit_files=(
            "timelapse-edge.service",
            "timelapse-totp.service",
            "timelapse-new.service",
        ),
        health_timeout_s=10,
        repo=repo,
    )

    calls = []

    def fake_systemctl(argv):
        calls.append(list(argv))
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    result = guard_pending_app_update(
        pending,
        timeout_s=0,
        systemd_dir=systemd_dir,
        systemctl_runner=fake_systemctl,
        restart_service=False,
        report_rollback=False,
    )

    assert result["ok"] is True
    assert result["state"] == "rolled_back_by_guard"
    assert (edge / "agent.py").read_text() == "old-agent"
    assert not (edge / "new_feature.py").exists()
    assert json.loads((edge / ".timelapse-release.json").read_text()) == previous_receipt
    assert (systemd_dir / "timelapse-edge.service").read_text() == "old-unit"
    assert (systemd_dir / "timelapse-totp.service").read_text() == "old-totp-unit"
    assert not (systemd_dir / "timelapse-new.service").exists()
    assert ["systemctl", "stop", "timelapse-new.service"] in calls
    assert ["systemctl", "daemon-reload"] in calls
    assert ["systemctl", "try-restart", "timelapse-totp.service"] in calls
    marker = load_pending_app_update(pending)
    assert marker["state"] == "rolled_back_by_guard"
    assert marker["rollback_reason"] == "post_restart_health_timeout"


def test_health_confirmation_prevents_guard_rollback(tmp_path: Path):
    repo = tmp_path / "timelapse"
    (repo / "edge").mkdir(parents=True)
    (repo / "edge" / "agent.py").write_text("candidate")
    recovery = _make_recovery_root(tmp_path)
    pending = pending_app_update_path(repo)
    write_pending_app_update(
        pending,
        update_id=7,
        artifact=_artifact(),
        recovery_dir=recovery,
        repo=repo,
    )
    mark_pending_app_update_health_confirmed(pending)

    result = guard_pending_app_update(
        pending,
        timeout_s=0,
        systemctl_runner=lambda argv: None,
        restart_service=False,
        report_rollback=False,
    )
    assert result == {"ok": True, "state": "health_confirmed"}
    assert (repo / "edge" / "agent.py").read_text() == "candidate"


def test_health_probe_requires_stability_window_before_confirmation(tmp_path: Path):
    from datetime import datetime, timedelta, timezone

    repo = tmp_path / "timelapse"
    (repo / "edge").mkdir(parents=True)
    recovery = _make_recovery_root(tmp_path)
    pending = pending_app_update_path(repo)
    write_pending_app_update(
        pending,
        update_id=7,
        artifact=_artifact(),
        recovery_dir=recovery,
        repo=repo,
    )

    first = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)
    probe = record_pending_app_update_health_probe(
        pending,
        stability_s=600,
        checks={"release_receipt_matches_artifact": True},
        now=first,
    )
    assert probe["state"] == "awaiting_restart_health"
    assert probe["health_elapsed_s"] == 0

    confirmed = record_pending_app_update_health_probe(
        pending,
        stability_s=600,
        checks={"release_receipt_matches_artifact": True},
        now=first + timedelta(seconds=600),
    )
    assert confirmed["state"] == "health_confirmed"
    assert confirmed["health_confirmed_at"]


def test_guard_runner_is_persisted_from_trusted_lifecycle_source(tmp_path: Path):
    recovery = _make_recovery_root(tmp_path)
    runner = write_post_restart_guard(recovery)
    guard_module = recovery / "update_lifecycle_guard.py"
    assert runner.is_file()
    assert guard_module.is_file()
    assert "guard_pending_app_update" in guard_module.read_text(encoding="utf-8")
    assert "bash\", \"-c" not in guard_module.read_text(encoding="utf-8")
    assert stat.S_IMODE(runner.stat().st_mode) == 0o700


def test_agent_defers_deployed_until_complete_startup_health_gate():
    source = Path("edge/agent.py").read_text(encoding="utf-8")
    startup_start = source.index("    def _startup(")
    startup_end = source.index("    def _auto_bootstrap_cameras(", startup_start)
    startup = source[startup_start:startup_end]
    assert startup.index("self._sync_captures()") < startup.index("self._finalize_pending_app_update_health()")

    update_check_start = source.index("    def _check_and_apply_updates(")
    update_check_end = source.index("    def _run_update(", update_check_start)
    update_check = source[update_check_start:update_check_end]
    assert update_check.index("self._reconcile_pending_app_update()") < update_check.index("/updates/policy/")

    installer_start = source.index("    def _run_artifact_app_update(")
    installer_end = source.index("    def _run_artifact_os_update(", installer_start)
    installer = source[installer_start:installer_end]
    assert "write_pending_app_update(" in installer
    assert "write_post_restart_guard(" in installer
    assert 'self._report_update(update_id, "deployed")' not in installer
    assert "awaiting_post_restart_health" in installer
    assert "rollback_ready = False" in installer
    assert "if rollback_ready and backup.exists()" in installer
    assert "post_restart_guard_not_active" in installer
    first_unit_loop = installer.index("Complete the recovery snapshot")
    active_unit_copy = installer.index("_shutil.copy2(source, target)", first_unit_loop)
    missing_unit_gate = installer.index("managed_systemd_unit_missing", first_unit_loop)
    assert missing_unit_gate < active_unit_copy


def test_watchdog_applies_device_relay_safety_state_from_edge_config():
    source = Path("edge/scripts/watchdog.sh").read_text(encoding="utf-8")
    assert 'RELAY_GPIO_PIN="${TIMELAPSE_RELAY_PIN:-18}"' not in source
    assert "resolve_camera_relay_gpio_pin()" in source
    assert "resolve_modem_relay_gpio_pin()" in source
    assert 'read_config_value "camera" "relay_gpio_pin"' in source
    assert 'read_config_value "modem" "modem_relay_gpio_pin"' in source
    assert "camera relay (camera off)" in source
    assert "modem relay (modem on)" in source
    assert "camera.relay_gpio_pin missing or invalid" in source
    assert "refusing relay safety action" in source
