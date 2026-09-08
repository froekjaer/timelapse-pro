"""Regression contracts for the dependency-free local Edge terminal."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "edge/scripts/totp-service.py").read_text(encoding="utf-8")


def test_shell_uses_forked_controlling_tty_for_bash_job_control():
    assert "child_pid, master_fd = pty.fork()" in SOURCE
    assert "os.execvpe(BASH_PATH, [BASH_PATH, \"-l\"], env)" in SOURCE
    assert "pty.openpty()" not in SOURCE
    assert "subprocess.Popen(" not in SOURCE[SOURCE.index('@app.websocket("/mgmt/cli/bash/ws")'):]


def test_shell_cleanup_terminates_and_reaps_child():
    assert "os.kill(child_pid, signal.SIGTERM)" in SOURCE
    assert "os.kill(child_pid, signal.SIGKILL)" in SOURCE
    assert "os.waitpid(child_pid, 0)" in SOURCE


def test_fallback_renderer_does_not_expose_ansi_control_sequences():
    assert "function renderShellOutput(data)" in SOURCE
    assert ".replace(/\\\\x1b\\\\[[" in SOURCE
    assert "renderShellOutput(event.data)" in SOURCE
