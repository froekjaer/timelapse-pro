# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — SSH Tunnel Manager (Edge)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 1.0.0
# Dato     : 06. maj 2026
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
#   1.0.0  06-maj-2026  Sprint C: Initial SSH tunnel manager
# ═══════════════════════════════════════════════════════════════════════════
"""
TimeLapse Pro — Reverse SSH Tunnel Manager
==========================================
Håndterer oprettelse og overvågning af reverse SSH tunnels fra edge til headend.

Funktioner:
  - Start/stop tunnel baseret på config
  - Auto-start ved API-tab (auto_on_api_loss)
  - Fallback til sekundær endpoint ved fejl
  - Notificering af headend når tunnel er klar
  - Fuld audit via headend API

Config-struktur (i device_config):
  ssh_tunnel:
    enabled: true
    primary:  "tunnel@timelapse.froekjaer.dk:22"
    fallback: "tunnel@backup.froekjaer.dk:22"
    remote_port: 2201          # unik pr. device
    local_port: 22
    extra_forwards:
      - remote_port: 2301
        local_port: 8090
        name: lab_video
    key_file: "/opt/timelapse/edge/ssh/tunnel_key"
    auto_on_api_loss: true
    auto_on_api_loss_threshold_s: 300
    deny: false                # true = aldrig start tunnel

SABSA: Accountability — alle sessioner logges til headend
       Confidentiality — key-baseret auth, ingen passwords
       Availability    — fallback endpoint ved fejl
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

TUNNEL_CHECK_INTERVAL_S = 30     # tjek tunnel status hvert 30 sek
CONNECT_TIMEOUT_S       = 15     # SSH connect timeout
KEEPALIVE_INTERVAL_S    = 60     # ServerAliveInterval
KEEPALIVE_COUNT_MAX     = 3      # ServerAliveCountMax


class SshTunnelManager:
    """
    Styrer én reverse SSH tunnel fra edge til headend.

    Bruges af agent.py:
        self._tunnel = SshTunnelManager(config, api_client)
        self._tunnel.start()           # starter overvågningsloop i baggrund
        self._tunnel.request_connect() # tving forbindelse nu
        self._tunnel.stop()            # stop tunnelen
    """

    def __init__(self, config: dict, api_client):
        self._cfg        = config
        self._api        = api_client
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._running    = False
        self._connected  = False
        self._using_fallback = False
        self._connect_time: Optional[float] = None
        self._lock       = threading.Lock()
        self._stderr_lock = threading.Lock()
        self._stderr_tail = deque(maxlen=20)
        self._stderr_thread: Optional[threading.Thread] = None

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self):
        """Start tunnel-overvågningsloop i baggrundstråd."""
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, name="ssh-tunnel", daemon=True
        )
        self._thread.start()
        log.info("SSH tunnel manager startet")


    def apply_config(self, tunnel_cfg: dict) -> None:
        """
        Anvend tunnel-config live uden agent-genstart.
        enabled → always_on da loop bruger always_on til at styre forbindelsen.
        """
        enabled = tunnel_cfg.get("enabled", False)
        deny    = tunnel_cfg.get("deny", False)

        # Map enabled til always_on som loop'en forstår
        updated = dict(tunnel_cfg)
        updated["always_on"] = enabled and not deny

        self._cfg["ssh_tunnel"] = updated
        log.info("SSH tunnel: live config apply — enabled=%s always_on=%s", enabled, updated["always_on"])

        if not enabled or deny:
            if self._connected:
                log.info("SSH tunnel: deaktiveret via live config — stopper")
                self._disconnect()
        else:
            if not self._connected:
                log.info("SSH tunnel: aktiveret via live config — starter")
                self._connect()

    
    def stop(self ):
        """Stop tunnel og overvågningsloop."""
        self._running = False
        self._kill_tunnel()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        log.info("SSH tunnel manager stoppet")

    def request_connect(self):
        """Anmod om øjeblikkelig tunnelforbindelse (bruges fra agent ved API-tab)."""
        if not self._is_allowed():
            log.warning("SSH tunnel: forbrug afvist (deny=true eller ikke enabled)")
            return
        with self._lock:
            if not self._connected:
                log.info("SSH tunnel: øjeblikkelig connect anmodet")
                self._connect()

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Config helpers ─────────────────────────────────────────────────────

    def _tunnel_cfg(self) -> dict:
        return self._cfg.get("ssh_tunnel", {})

    def _is_enabled(self) -> bool:
        return bool(self._tunnel_cfg().get("enabled", False))

    def _is_denied(self) -> bool:
        """deny=true på customer/site/device niveau — override alt."""
        return bool(self._tunnel_cfg().get("deny", False))

    def _is_allowed(self) -> bool:
        return self._is_enabled() and not self._is_denied()

    def _primary_endpoint(self) -> Optional[str]:
        return self._tunnel_cfg().get("primary")

    def _fallback_endpoint(self) -> Optional[str]:
        return self._tunnel_cfg().get("fallback")

    def _remote_port(self) -> int:
        return int(self._tunnel_cfg().get("remote_port", 2200))

    def _local_port(self) -> int:
        return int(self._tunnel_cfg().get("local_port", 22))

    def _remote_forwards(self) -> list[tuple[int, int, str]]:
        forwards = [(self._remote_port(), self._local_port(), "ssh")]
        for item in self._tunnel_cfg().get("extra_forwards", []) or []:
            try:
                remote_port = int(item.get("remote_port"))
                local_port = int(item.get("local_port"))
                name = str(item.get("name") or f"{remote_port}->{local_port}")
                if remote_port > 0 and local_port > 0:
                    forwards.append((remote_port, local_port, name))
            except Exception:
                log.warning("SSH tunnel: ignorerer ugyldig extra_forward: %r", item)
        return forwards

    def _key_file(self) -> Optional[Path]:
        kf = self._tunnel_cfg().get("key_file", "/opt/timelapse/edge/ssh/tunnel_key")
        p = Path(kf)
        return p if p.exists() else None

    def _auto_on_api_loss(self) -> bool:
        return bool(self._tunnel_cfg().get("auto_on_api_loss", True))

    def _api_loss_threshold_s(self) -> int:
        return int(self._tunnel_cfg().get("auto_on_api_loss_threshold_s", 300))

    # ── Tunnel management ──────────────────────────────────────────────────

    def _loop(self):
        """Baggrunds-overvågningsloop."""
        api_last_ok = time.monotonic()

        while self._running:
            try:
                # Genindlæs config (kan ændre sig)
                tcfg = self._tunnel_cfg()

                # Tjek om tunnel er konfigureret
                if not self._is_allowed():
                    if self._connected:
                        log.info("SSH tunnel: disabled/denied fra config — afbryder")
                        self._disconnect()
                    time.sleep(TUNNEL_CHECK_INTERVAL_S)
                    continue

                # Tjek om tunnel-processen stadig kører
                with self._lock:
                    if self._proc and self._proc.poll() is not None:
                        log.warning("SSH tunnel: proces termineret — reconnect")
                        self._connected = False
                        self._proc = None

                # Start tunnel:
                # 1. Altid aktiv hvis enabled=true (always_on mode)
                # 2. Auto-start ved API-tab hvis auto_on_api_loss=true
                if not self._connected:
                    api_ok = self._api.ping()
                    if api_ok:
                        api_last_ok = time.monotonic()
                    else:
                        elapsed = time.monotonic() - api_last_ok

                    always_on = self._tunnel_cfg().get("always_on", True)  # default: altid aktiv
                    api_loss  = self._auto_on_api_loss() and not api_ok and                                 (time.monotonic() - api_last_ok) >= self._api_loss_threshold_s()

                    if always_on:
                        if not api_ok:
                            log.info("SSH tunnel: enabled=True — starter tunnel (API utilgængeligt)")
                        else:
                            log.info("SSH tunnel: enabled=True — starter tunnel")
                        self._connect()
                    elif api_loss:
                        log.warning(
                            "SSH tunnel: API utilgængeligt i %.0fs — starter tunnel",
                            time.monotonic() - api_last_ok
                        )
                        self._connect()

                # Tjek om tunnel stadig er alive
                if self._connected:
                    if not self._check_alive():
                        log.warning("SSH tunnel: keepalive fejlet — reconnect")
                        self._disconnect()
                        time.sleep(5)
                        self._connect()

            except Exception as exc:
                log.error("SSH tunnel loop fejl: %s", exc)

            time.sleep(TUNNEL_CHECK_INTERVAL_S)

    def _connect(self):
        """Opret SSH reverse tunnel — prøv primary, derefter fallback."""
        endpoint = self._primary_endpoint()
        self._using_fallback = False

        if not endpoint:
            log.error("SSH tunnel: ingen primary endpoint konfigureret")
            return

        success = self._try_connect(endpoint)
        if not success:
            fallback = self._fallback_endpoint()
            if fallback:
                log.info("SSH tunnel: primary fejlede — prøver fallback")
                self._using_fallback = True
                success = self._try_connect(fallback)

        if success:
            self._connected = True
            self._connect_time = time.monotonic()
            log.info(
                "SSH tunnel: forbundet (%s) remote_port=%d local_port=%d",
                "fallback" if self._using_fallback else "primary",
                self._remote_port(),
                self._local_port(),
            )
            self._notify_connected()
        else:
            log.error("SSH tunnel: alle endpoints fejlede")
            self._notify_failed()

    def _start_stderr_drain(self, proc: subprocess.Popen) -> None:
        """Drain SSH stderr continuously while retaining only a bounded diagnostic tail."""
        with self._stderr_lock:
            self._stderr_tail.clear()
        thread = threading.Thread(
            target=self._drain_stderr,
            args=(proc,),
            name="ssh-tunnel-stderr",
            daemon=True,
        )
        self._stderr_thread = thread
        thread.start()

    def _drain_stderr(self, proc: subprocess.Popen) -> None:
        stream = proc.stderr
        if stream is None:
            return
        try:
            # Limit each read as well as the retained deque so a malformed or
            # noisy SSH process cannot create unbounded memory pressure.
            for raw in iter(lambda: stream.readline(2048), b""):
                line = raw.decode(errors="replace").strip()
                if not line:
                    continue
                with self._stderr_lock:
                    self._stderr_tail.append(line[-1000:])
        except Exception as exc:
            log.debug("SSH tunnel: stderr drain sluttede med fejl: %s", exc)
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _stderr_summary(self) -> str:
        with self._stderr_lock:
            return "\n".join(self._stderr_tail)[-4000:]

    def _join_stderr_drain(self, timeout: float = 1.0) -> None:
        thread = self._stderr_thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        if thread and not thread.is_alive() and self._stderr_thread is thread:
            self._stderr_thread = None

    def _try_connect(self, endpoint: str) -> bool:
        """Forsøg forbindelse til et enkelt endpoint."""
        try:
            # Parse endpoint: "user@host:port"
            if "@" not in endpoint:
                log.error("SSH tunnel: ugyldigt endpoint format: %s", endpoint)
                return False

            user_host, _, port_str = endpoint.rpartition(":")
            ssh_port = int(port_str) if port_str.isdigit() else 22
            user, _, host = user_host.partition("@")

            key_file = self._key_file()
            if not key_file:
                log.error("SSH tunnel: nøglefil ikke fundet — konfigurer ssh_tunnel.key_file")
                return False

            cmd = [
                "ssh",
                "-N",                                           # ingen kommando
                "-p", str(ssh_port),
                "-i", str(key_file),
                "-o", f"StrictHostKeyChecking={self._tunnel_cfg().get('strict_host_checking', 'accept-new')}",
                "-o", f"ConnectTimeout={CONNECT_TIMEOUT_S}",
                "-o", f"ServerAliveInterval={KEEPALIVE_INTERVAL_S}",
                "-o", f"ServerAliveCountMax={KEEPALIVE_COUNT_MAX}",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "BatchMode=yes",                          # ingen password prompts
                "-o", f"UserKnownHostsFile={str(key_file.parent / 'known_hosts')}",
                f"{user}@{host}",
            ]
            for remote_port, local_port, name in reversed(self._remote_forwards()):
                cmd[2:2] = ["-R", f"{remote_port}:localhost:{local_port}"]
                log.info("SSH tunnel forward: %s remote=%d local=%d", name, remote_port, local_port)

            log.info("SSH tunnel: starter %s@%s:%d remote_port=%d",
                     user, host, ssh_port, self._remote_port())

            with self._lock:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                proc = self._proc
            self._start_stderr_drain(proc)

            # Vent kort og tjek at processen ikke straks fejlede.  stderr is
            # drained concurrently, so a long-running tunnel cannot block on a
            # full pipe while we still retain a bounded failure tail.
            time.sleep(3)
            if proc.poll() is not None:
                self._join_stderr_drain(timeout=1.0)
                stderr = self._stderr_summary()
                log.error("SSH tunnel: connect fejlede: %s", stderr[:200])
                with self._lock:
                    if self._proc is proc:
                        self._proc = None
                return False

            return True

        except Exception as exc:
            log.error("SSH tunnel: _try_connect fejl: %s", exc)
            return False

    def _disconnect(self):
        """Afbryd tunnel og log varighed."""
        duration_s = None
        if self._connect_time:
            duration_s = int(time.monotonic() - self._connect_time)
        self._kill_tunnel()
        self._connected = False
        self._connect_time = None
        self._notify_disconnected(duration_s)
        log.info("SSH tunnel: afbrudt (varighed=%ss)", duration_s)

    def _kill_tunnel(self):
        """Dræb SSH-processen og luk stderr-drain deterministisk."""
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass
        self._join_stderr_drain(timeout=1.0)

    def _check_alive(self) -> bool:
        """Returnerer True hvis tunnel-processen stadig kører."""
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    # ── Headend notifikationer ─────────────────────────────────────────────

    def _notify_connected(self):
        """Notificer headend om aktiv tunnel."""
        try:
            self._api._post("/ssh-tunnel/event", {
                "device_id":   self._api._device_id,
                "event":       "connected",
                "remote_port": self._remote_port(),
                "local_port":  self._local_port(),
                "using_fallback": self._using_fallback,
                "timestamp":   self._now_iso(),
            })
        except Exception as exc:
            log.warning("SSH tunnel: notifikation fejlede: %s", exc)

    def _notify_disconnected(self, duration_s: Optional[int]):
        """Notificer headend om afbrudt tunnel."""
        try:
            self._api._post("/ssh-tunnel/event", {
                "device_id":  self._api._device_id,
                "event":      "disconnected",
                "remote_port": self._remote_port(),
                "duration_s": duration_s,
                "timestamp":  self._now_iso(),
            })
        except Exception as exc:
            log.warning("SSH tunnel: disconnect notifikation fejlede: %s", exc)

    def _notify_failed(self):
        """Notificer headend om fejlet connect-forsøg."""
        try:
            self._api._post("/ssh-tunnel/event", {
                "device_id":  self._api._device_id,
                "event":      "failed",
                "remote_port": self._remote_port(),
                "timestamp":  self._now_iso(),
            })
        except Exception as exc:
            log.warning("SSH tunnel: fejl-notifikation fejlede: %s", exc)

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
