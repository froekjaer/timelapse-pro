import io
from pathlib import Path

from edge.tunnel.ssh_manager import SshTunnelManager


class DummyApi:
    _device_id = "TL-TEST"

    def ping(self):
        return True

    def _post(self, *_args, **_kwargs):
        return True, {}


class DummyProc:
    def __init__(self, stderr=b""):
        self.stderr = io.BytesIO(stderr)
        self.terminated = False
        self.killed = False
        self.waited = []

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.waited.append(timeout)
        return 0

    def poll(self):
        return None


def _manager():
    return SshTunnelManager({"ssh_tunnel": {}}, DummyApi())


def test_stderr_drain_is_bounded_and_keeps_latest_diagnostics():
    proc = DummyProc(b"".join(f"line-{i}\n".encode() for i in range(60)))
    manager = _manager()
    manager._start_stderr_drain(proc)
    manager._join_stderr_drain(timeout=2.0)

    summary = manager._stderr_summary()
    assert "line-59" in summary
    assert "line-0\n" not in summary
    assert len(manager._stderr_tail) <= 20
    assert manager._stderr_thread is None


def test_kill_tunnel_terminates_process_and_joins_reader():
    proc = DummyProc(b"diagnostic\n")
    manager = _manager()
    manager._proc = proc
    manager._start_stderr_drain(proc)

    manager._kill_tunnel()

    assert proc.terminated is True
    assert manager._proc is None
    assert manager._stderr_thread is None
    assert "diagnostic" in manager._stderr_summary()


def test_source_has_no_undrained_direct_stderr_read_contract():
    source = Path("edge/tunnel/ssh_manager.py").read_text(encoding="utf-8")
    assert "stderr=subprocess.PIPE" in source
    assert "self._start_stderr_drain(proc)" in source
    assert "stream.readline(2048)" in source
    assert "deque(maxlen=20)" in source
    assert ".stderr.read()" not in source
    assert "self._join_stderr_drain(timeout=1.0)" in source
