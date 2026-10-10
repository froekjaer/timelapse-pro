"""Wake an Edge through its SSH tunnel when the Headend has something for it.

Peter, 2026-10-10: LAB mode (and any config change or approved update) took
up to 5-10 minutes to reach an Edge, because the Edge only polls every five
minutes. His design: while the reverse tunnel is up, the Headend sends a
"poll now" through it with a shared key that cannot be used for anything else
and cannot be reached from outside the tunnel.

On the Edge (edge/scripts/timelapse_system_baseline.py, step "wake") the key
is accepted only for the `tlwake` account, only from 127.0.0.1/::1 (i.e.
through the tunnel), with `restrict` and a forced command that merely bumps
/run/timelapse/wake-request; the agent sees that and runs its normal
authenticated /sync at once. No data travels over this path, and when nothing
changes there is no traffic at all.

Whether an Edge may be woken is configurable in the configuration hierarchy
(global/customer/site/device/camera) as `system.headend_wake` (default on,
Peter 2026-10-10). The Edge enforces it itself — with it off the agent
removes the wake key, so its sshd refuses it — and this watcher does not try.

Here: a background watcher computes each device's wake token (config_version
+ approved updates) every few seconds and, when it changes, connects through
the tunnel port, refuses unless the Edge's host key matches the trusted
fingerprint (same registry as the browser terminal), and authenticates with
the wake key. Failures only mean the Edge picks the change up at its next
normal poll.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import threading
import time
from pathlib import Path

log = logging.getLogger("headend")

WAKE_USER = "tlwake"
CHECK_INTERVAL_S = 3.0
TRUSTED_HOST_STATES = ("trusted", "verified")


def wake_key_path() -> Path:
    return Path(os.getenv("TIMELAPSE_EDGE_WAKE_KEY", "~/.ssh/timelapse_wake_ed25519")).expanduser()


def wake_token(db, device_id: str) -> str:
    """Changes whenever the Edge has something new to pick up via /sync."""
    from database import Device, PendingUpdate

    device = db.query(Device).filter_by(device_id=device_id).first()
    approved = sorted(
        u.id for u in db.query(PendingUpdate).filter(
            PendingUpdate.status.in_(["approved", "rollback_requested"])
        ).all()
    )
    raw = f"{getattr(device, 'config_version', '') or ''}|{approved}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def fingerprint_sha256(key) -> str:
    return "SHA256:" + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode("ascii").rstrip("=")


def send_wake(port: int, trusted_fingerprint: str, key_path: Path | None = None,
              host: str = "127.0.0.1", timeout: float = 8.0, transport_factory=None) -> tuple[bool, str]:
    """Connect through the tunnel port and trigger the Edge's forced wake command.

    Fail closed: no connection is authenticated unless the server's host key
    matches the trusted fingerprint.
    """
    import paramiko

    key_path = key_path or wake_key_path()
    if not key_path.is_file():
        return False, f"wake key missing: {key_path}"
    factory = transport_factory or paramiko.Transport
    transport = None
    try:
        transport = factory((host, int(port)))
        transport.start_client(timeout=timeout)
        observed = fingerprint_sha256(transport.get_remote_server_key())
        if observed != trusted_fingerprint:
            return False, f"host key mismatch ({observed} != {trusted_fingerprint})"
        transport.auth_publickey(WAKE_USER, paramiko.Ed25519Key.from_private_key_file(str(key_path)))
        channel = transport.open_session(timeout=timeout)
        channel.settimeout(timeout)
        channel.exec_command("wake")          # ignored: the Edge runs its forced command
        status = channel.recv_exit_status()
        return status == 0, f"exit {status}"
    except Exception as exc:
        return False, str(exc)
    finally:
        if transport is not None:
            try:
                transport.close()
            except Exception:
                pass


def _tunnel_targets(db) -> dict[str, tuple[int, str]]:
    """device_id -> (tunnel port, trusted host-key fingerprint) for connected tunnels."""
    from database import SshHostKeyTrust, SshTunnelLog

    targets: dict[str, tuple[int, str]] = {}
    for trust in db.query(SshHostKeyTrust).filter(SshHostKeyTrust.trusted_state.in_(TRUSTED_HOST_STATES)).all():
        latest = (db.query(SshTunnelLog).filter(SshTunnelLog.device_id == trust.device_id)
                  .order_by(SshTunnelLog.event_at.desc()).first())
        if latest and latest.event == "connected" and latest.remote_port:
            targets[trust.device_id] = (int(latest.remote_port), trust.fingerprint_sha256)
    return targets


def wake_allowed(config: dict) -> bool:
    """system.headend_wake from the merged hierarchy (global → device →
    customer → site → camera). Missing = allowed (factory default)."""
    value = ((config or {}).get("system") or {}).get("headend_wake", True)
    return str(value).strip().lower() not in {"false", "0", "no", "off", "none"}


def _effective_config(db, device_id: str) -> dict:
    from main import get_config   # lazy: main imports the router that starts us

    return get_config(device_id, _auth=None, db=db)


class EdgeWakeWatcher:
    def __init__(self, session_factory, sender=send_wake):
        self._session_factory = session_factory
        self._sender = sender
        self._tokens: dict[str, str] = {}

    def check_once(self) -> list[str]:
        """One pass; returns the device_ids a wake was sent to."""
        db = self._session_factory()
        try:
            targets = _tunnel_targets(db)
            changed = []
            for device_id in targets:
                token = wake_token(db, device_id)
                previous = self._tokens.get(device_id)
                self._tokens[device_id] = token
                if previous is not None and previous != token:
                    # Only now (something changed) pay for the merged config.
                    if wake_allowed(_effective_config(db, device_id)):
                        changed.append(device_id)
                    else:
                        log.info("Edge wake til %s ikke tilladt (system.headend_wake=false)", device_id)
        finally:
            db.close()
        for device_id in changed:
            port, fingerprint = targets[device_id]
            threading.Thread(target=self._wake, args=(device_id, port, fingerprint),
                             name=f"edge-wake-{device_id}", daemon=True).start()
        return changed

    def _wake(self, device_id: str, port: int, fingerprint: str) -> None:
        ok, detail = self._sender(port, fingerprint)
        if ok:
            log.info("Edge wake sendt til %s via tunnel-port %s", device_id, port)
        else:
            log.warning("Edge wake til %s fejlede (Edgen henter ændringen ved næste poll): %s", device_id, detail)

    def run_forever(self) -> None:
        while True:
            try:
                self.check_once()
            except Exception as exc:
                log.warning("Edge wake watcher fejl: %s", exc)
            time.sleep(CHECK_INTERVAL_S)


_started = False
_start_lock = threading.Lock()


def _disabled() -> bool:
    import sys

    return "pytest" in sys.modules or os.getenv("TIMELAPSE_EDGE_WAKE", "1").strip().lower() in {"0", "false", "off", "no"}


def start_edge_wake_watcher() -> bool:
    """Start the watcher once per process. Idempotent: FastAPI ran the router's
    startup handler twice (copied on include_router *and* via the merged
    router lifespan), which started two watchers and sent every wake twice
    (seen live 2026-10-10)."""
    global _started
    with _start_lock:
        if _started:
            return False
        _started = True
    if _disabled():
        return False
    from database import SessionLocal

    threading.Thread(target=EdgeWakeWatcher(SessionLocal).run_forever, name="edge-wake-watcher", daemon=True).start()
    log.info("Edge wake watcher startet (wake gennem SSH-tunnel ved ændringer)")
    return True
