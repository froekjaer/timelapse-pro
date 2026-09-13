"""Regression contracts for the local Edge terminal (xterm.js frontend, forked PTY backend).

2026-09-13: the dependency-free ANSI-stripping textarea renderer this module
used to guard (test_fallback_renderer_does_not_expose_ansi_control_sequences)
was replaced with a real terminal emulator (xterm.js, vendored locally under
edge/scripts/static/xterm/ - same library Headend's own "Åbn terminal" SSH
view uses). Physical testing found the textarea renderer could not support
Ctrl-C/job control, Tab completion, history (arrow keys), Home/End or resize
correctly. See Dokumentation/ for the capability-regression writeup: a real
xterm.js implementation for this exact endpoint already existed and was
live-tested on a real Edge (commit d67ca26d, 2026-08-06) but was never merged
- mainline instead kept the textarea fallback through PR #198 and #238.
"""

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


def test_frontend_uses_vendored_xterm_not_a_hand_rolled_renderer():
    assert "new Terminal(" in SOURCE
    assert "term.onData(" in SOURCE
    assert "/mgmt/static/xterm/xterm.js" in SOURCE
    assert "/mgmt/static/xterm/xterm.css" in SOURCE
    assert "function renderShellOutput(data)" not in SOURCE
    assert "<textarea" not in SOURCE


def test_xterm_assets_are_vendored_locally_not_loaded_from_a_cdn():
    xterm_dir = ROOT / "edge/scripts/static/xterm"
    assert (xterm_dir / "xterm.js").is_file()
    assert (xterm_dir / "xterm.css").is_file()
    assert (xterm_dir / "addon-fit.js").is_file()
    assert (xterm_dir / "LICENSE").is_file()
    assert "cdn." not in SOURCE
    assert "unpkg.com" not in SOURCE
    assert "jsdelivr" not in SOURCE


def test_shell_resize_is_handled_via_pty_winsize_ioctl():
    assert "RESIZE_PREFIX" in SOURCE
    assert "TIOCSWINSZ" in SOURCE
    assert "FitAddon" in SOURCE
