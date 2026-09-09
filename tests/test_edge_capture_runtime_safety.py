from pathlib import Path


ROOT = Path(__file__).parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_tick_claims_capture_slot_before_sync_poll() -> None:
    source = _source("edge/agent.py")
    tick = source.split("def _tick(self, mode: str) -> None:", 1)[1].split("\n    def ", 1)[0]
    assert tick.index("self._scheduled_capture_slot") < tick.index("self._run_sync()")
    assert "A slow or unreachable Headend must never prevent" in tick


def test_capture_cycle_syncs_via_bounded_sync_captures() -> None:
    # _sync_captures() itself is bounded (breaks after the first failed
    # request — see test_failed_backlog_sync_stops_after_first_network_failure),
    # so calling it here does not risk walking an unbounded network backlog.
    # It must still run so a fresh capture reaches Headend promptly instead of
    # waiting for the next sync_interval poll — see
    # test_agent_integrity.py::test_sync_captures_in_capture_cycle.
    source = _source("edge/agent.py")
    cycle = source.split("def _do_capture_cycle(", 1)[1].split("\n    def ", 1)[0]
    assert "self._sync_captures()" in cycle
    assert "self._upload_capture_transports(" in cycle


def test_failed_backlog_sync_stops_after_first_network_failure() -> None:
    source = _source("edge/agent.py")
    sync = source.split("def _sync_captures(", 1)[1].split("\n    def ", 1)[0]
    retry = source.split("def _retry_pending_api_uploads(", 1)[1].split("\n    def ", 1)[0]
    assert "Capture sync stopped after first failed request" in sync
    assert "API upload retry stopped after first failed request" in retry
    assert "break" in sync and "break" in retry


def test_capture_cycle_syncs_gps_time_before_camera_power_on() -> None:
    # The camera and GPS module share a power rail (Peter, 2026-09-09): GPS
    # loses its fix every time the camera powers on/captures, so an
    # independent periodic timer can land its own correction attempt right
    # after a capture — exactly when GPS has just dropped out. Syncing here,
    # before camera power-on, is the only reliable way to catch GPS time
    # from before THIS cycle's own dip.
    source = _source("edge/agent.py")
    cycle = source.split("def _do_capture_cycle(", 1)[1].split("\n    def ", 1)[0]
    assert cycle.index("self._sync_time_from_gps_before_capture()") < cycle.index('self._camera_power_on("capture cycle")')


def test_gps_time_sync_never_raises_or_blocks_capture() -> None:
    source = _source("edge/agent.py")
    method = source.split("def _sync_time_from_gps_before_capture(self)", 1)[1].split("\n    def ", 1)[0]
    assert "except Exception" in method
    assert "Never raises" in source.split("def _sync_time_from_gps_before_capture(self)", 1)[1][:600]


def test_gps_time_sync_respects_step_threshold() -> None:
    source = _source("edge/agent.py")
    assert "_TIME_SYNC_STEP_THRESHOLD_S = 5" in source
    method = source.split("def _sync_time_from_gps_before_capture(self)", 1)[1].split("\n    def ", 1)[0]
    assert "self._TIME_SYNC_STEP_THRESHOLD_S" in method


def test_gps_time_reader_requires_2d_or_3d_fix() -> None:
    source = _source("edge/agent.py")
    reader = source.split("def _read_gps_time(", 1)[1].split("\n    def ", 1)[0]
    assert 'message.get("class") != "TPV"' in reader
    assert 'int(message.get("mode") or 0) < 2' in reader


def test_gps_time_reader_requires_two_consistent_readings_before_returning() -> None:
    # Peter, 2026-09-09: the camera and GPS module share a power rail, so
    # GPS loses power (and needs to reacquire) on every capture. gpsd's
    # first reading right after power returns, before the fix has settled,
    # can be a transient bad value — a single TPV read isn't enough to
    # trust. Deliberately does not rely on disabling chrony's SHM refclock
    # "trust" flag: these devices have no RTC, so GPS is the only time
    # source to fall back on.
    source = _source("edge/agent.py")
    assert "_GPS_STABILITY_TOLERANCE_S = 2" in source
    reader = source.split("def _read_gps_time(", 1)[1].split("\n    def ", 1)[0]
    assert "readings.append((time.monotonic(), candidate))" in reader
    assert "len(readings) >= 2" in reader
    assert "cls._GPS_STABILITY_TOLERANCE_S" in reader


def test_gps_time_reader_uses_wall_clock_deadline_not_fixed_line_count() -> None:
    # Regression class already fixed once for the position-reading GPS
    # helper (gphoto2_driver.py _read_gpsd_fix(), 2026-07-03): `gpspipe -w -n
    # N` counts ALL JSON messages, not just TPV, so a fixed N needs far more
    # wall-clock time than any sane subprocess timeout allows — gpspipe was
    # always killed before it could exit on its own, fix or no fix. This
    # reader mirrors that helper's fix: stop line-by-line as soon as a
    # usable TPV arrives, bounded only by a wall-clock deadline.
    source = _source("edge/agent.py")
    reader = source.split("def _read_gps_time(", 1)[1].split("\n    def ", 1)[0]
    assert '["gpspipe", "-w"]' in reader
    assert '"-n"' not in reader
    assert "_select.select(" in reader
    assert "deadline" in reader


def test_edge_service_creates_persistent_breakglass_log_root_before_agent() -> None:
    source = _source("edge/scripts/timelapse-edge.service")
    assert "ExecStartPre=/bin/mkdir -p /var/log.hdd/timelapse/breakglass/sessions" in source


def test_new_edge_images_remove_competing_legacy_tunnel_unit() -> None:
    for path in ("headend/tools/Dockerfile.edge", "headend/tools/Dockerfile.edge.armhf"):
        source = _source(path)
        assert "rm -f /etc/systemd/system/timelapse-ssh-tunnel.service" in source
        assert "multi-user.target.wants/timelapse-ssh-tunnel.service" in source
