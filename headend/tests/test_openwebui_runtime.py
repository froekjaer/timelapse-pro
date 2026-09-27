import json
from types import SimpleNamespace

import openwebui_runtime as runtime


def test_service_status_parses_running_pid_and_health(monkeypatch):
    monkeypatch.setattr(runtime, "_launchctl", lambda *_args, **_kwargs: SimpleNamespace(
        returncode=0, stdout="state = running\n pid = 4242\n", stderr=""
    ))
    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    response = _Response()
    monkeypatch.setattr(runtime.urllib.request, "urlopen", lambda *_args, **_kwargs: response)

    status = runtime.service_status()

    assert status == {"running": True, "healthy": True, "pid": 4242}


def test_unload_ollama_models_requests_keep_alive_zero(monkeypatch):
    calls = []

    class _Response:
        status = 200

        def __init__(self, payload=b"{}"):
            self.payload = payload

        def read(self):
            return self.payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def fake_urlopen(request, timeout):
        if isinstance(request, str):
            return _Response(json.dumps({"models": [{"name": "qwen3-vl:8b"}]}).encode())
        calls.append(json.loads(request.data))
        return _Response()

    monkeypatch.setattr(runtime.urllib.request, "urlopen", fake_urlopen)

    assert runtime.unload_ollama_models() == ["qwen3-vl:8b"]
    assert calls == [{"model": "qwen3-vl:8b", "keep_alive": 0}]


def _recording_launchctl(monkeypatch, loaded=True):
    commands = []

    def fake(*args, **kwargs):
        commands.append((args, kwargs.get("privileged", False)))
        rc = 0 if (args[0] != "print" or loaded) else 113
        return SimpleNamespace(returncode=rc, stdout="", stderr="")

    monkeypatch.setattr(runtime, "_launchctl", fake)
    return commands


def test_stop_service_unloads_models_but_does_not_stop_ollama_daemon(monkeypatch):
    unloaded = []
    commands = _recording_launchctl(monkeypatch, loaded=True)
    monkeypatch.setattr(runtime, "unload_ollama_models", lambda: unloaded.append(True) or ["model"])

    runtime.stop_service()

    # bootout, not SIGTERM: the plist has KeepAlive=true, so launchd would
    # restart a SIGTERMed job immediately.
    assert (("bootout", runtime._target()), True) in commands
    assert unloaded == [True]
    assert all("ollama" not in " ".join(args).lower() for args, _ in commands)


def test_start_service_bootstraps_when_not_loaded(monkeypatch):
    commands = _recording_launchctl(monkeypatch, loaded=False)

    runtime.start_service()

    assert (("bootstrap", runtime._domain(), runtime._plist()), True) in commands


def test_start_service_kickstarts_when_loaded(monkeypatch):
    commands = _recording_launchctl(monkeypatch, loaded=True)

    runtime.start_service()

    assert (("kickstart", "-k", runtime._target()), True) in commands


def test_system_daemon_uses_system_domain_and_sudo(monkeypatch):
    """2026-09-27: the service is a system LaunchDaemon; targeting gui/<uid>
    failed with 'Could not find service ... in domain for user gui: 502'."""
    monkeypatch.setattr(runtime, "_is_system_daemon", lambda: True)
    assert runtime._target() == "system/dk.froekjaer.open-webui"
    assert runtime._plist() == "/Library/LaunchDaemons/dk.froekjaer.open-webui.plist"

    calls = []
    monkeypatch.setattr(runtime.subprocess, "run", lambda command, **_kw: calls.append(command) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    runtime._launchctl("print", runtime._target())
    runtime._launchctl("bootout", runtime._target(), privileged=True)
    assert calls[0][:2] == ["/bin/launchctl", "print"]
    assert calls[1][:4] == ["/usr/bin/sudo", "-n", "/bin/launchctl", "bootout"]


def test_user_agent_uses_gui_domain_without_sudo(monkeypatch):
    monkeypatch.setattr(runtime, "_is_system_daemon", lambda: False)
    assert runtime._target().startswith("gui/")
    calls = []
    monkeypatch.setattr(runtime.subprocess, "run", lambda command, **_kw: calls.append(command) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    runtime._launchctl("bootout", runtime._target(), privileged=True)
    assert calls[0][0] == "/bin/launchctl"
