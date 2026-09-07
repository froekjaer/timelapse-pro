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


def test_edge_service_creates_persistent_breakglass_log_root_before_agent() -> None:
    source = _source("edge/scripts/timelapse-edge.service")
    assert "ExecStartPre=/bin/mkdir -p /var/log.hdd/timelapse/breakglass/sessions" in source


def test_new_edge_images_remove_competing_legacy_tunnel_unit() -> None:
    for path in ("headend/tools/Dockerfile.edge", "headend/tools/Dockerfile.edge.armhf"):
        source = _source(path)
        assert "rm -f /etc/systemd/system/timelapse-ssh-tunnel.service" in source
        assert "multi-user.target.wants/timelapse-ssh-tunnel.service" in source
