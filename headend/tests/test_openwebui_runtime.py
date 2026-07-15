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


def test_stop_service_unloads_models_but_does_not_stop_ollama_daemon(monkeypatch):
    commands = []
    unloaded = []
    monkeypatch.setattr(runtime, "service_status", lambda: {"running": True})
    monkeypatch.setattr(runtime, "_launchctl", lambda *args, **_kwargs: commands.append(args) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(runtime, "unload_ollama_models", lambda: unloaded.append(True) or ["model"])

    runtime.stop_service()

    assert commands == [("kill", "SIGTERM", runtime._target())]
    assert unloaded == [True]
    assert all("ollama" not in " ".join(command).lower() for command in commands)
