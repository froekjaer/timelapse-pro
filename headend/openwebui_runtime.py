"""Small, auditable runtime controller for the optional Open WebUI service."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone


LABEL = "dk.froekjaer.open-webui"
# Open WebUI runs as a system LaunchDaemon (UserName=peter) on the Headend
# since 2026-07-07; older installs used a per-user LaunchAgent. Controlling a
# system-domain job needs root, via the existing NOPASSWD sudoers rule for
# /bin/launchctl (also used by the CI deploy job). Mutations use
# bootstrap/bootout because the plist has KeepAlive=true: a plain SIGTERM is
# restarted by launchd immediately and never actually stops the service.
SYSTEM_PLIST = f"/Library/LaunchDaemons/{LABEL}.plist"


def _is_system_daemon() -> bool:
    return os.path.exists(SYSTEM_PLIST)


def _domain() -> str:
    return "system" if _is_system_daemon() else f"gui/{os.getuid()}"


def _target() -> str:
    return f"{_domain()}/{LABEL}"


def _plist() -> str:
    return SYSTEM_PLIST if _is_system_daemon() else os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")


def _launchctl(*args: str, timeout: int = 15, privileged: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["/bin/launchctl", *args]
    if privileged and _is_system_daemon():
        command = ["/usr/bin/sudo", "-n", *command]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _is_loaded() -> bool:
    return _launchctl("print", _target()).returncode == 0


def service_status() -> dict:
    result = _launchctl("print", _target())
    output = f"{result.stdout}\n{result.stderr}"
    running = result.returncode == 0 and "state = running" in output
    pid = None
    for line in output.splitlines():
        if line.strip().startswith("pid ="):
            try:
                pid = int(line.split("=", 1)[1].strip())
            except ValueError:
                pass
            break
    healthy = False
    if running:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2) as response:
                healthy = response.status < 500
        except Exception:
            pass
    return {"running": running, "healthy": healthy, "pid": pid}


def start_service() -> None:
    if _is_loaded():
        result = _launchctl("kickstart", "-k", _target(), timeout=30, privileged=True)
    else:
        result = _launchctl("bootstrap", _domain(), _plist(), timeout=30, privileged=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "launchctl start failed").strip())


def stop_service() -> None:
    if _is_loaded():
        result = _launchctl("bootout", _target(), timeout=30, privileged=True)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "launchctl stop failed").strip())
    unload_ollama_models()


def unload_ollama_models() -> list[str]:
    """Unload model allocations while leaving the lightweight Ollama API available."""
    unloaded: list[str] = []
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=3) as response:
            models = json.loads(response.read()).get("models", [])
    except Exception:
        return unloaded
    for model in models:
        name = model.get("name") or model.get("model")
        if not name:
            continue
        body = json.dumps({"model": name, "keep_alive": 0}).encode()
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=15):
                unloaded.append(name)
        except Exception:
            continue
    return unloaded


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
