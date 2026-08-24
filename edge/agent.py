# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — agent.py (Edge Agent)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 3.2.0
# Dato     : 06. maj 2026
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
#   3.2.0  06-maj-2026  LAB capture bug fix: disconnect + power_off FØR
#                       _do_capture_cycle for at undgå dobbelt gphoto2-connect
#   3.1.0  12-apr-2026  Stabile USB symlinks via /dev/timelapse-camN
#                       _discover_cameras bruger udev i stedet for auto-detect
#                       Indenteringsfejl i _capture_single_camera rettet
#   3.0.0  12-apr-2026  Multi-kamera burst capture (threading)
#                       Auto-bootstrap sibling devices
#   2.9.0  12-apr-2026  relay_toggle lab_command
#   2.8.0  11-apr-2026  PTP busy relay power cycle recovery
#   2.7.0  11-apr-2026  focusmode=Manual, clear-update
#   2.6.0  10-apr-2026  _build_camera_commands, drift-check
#   2.5.0  10-apr-2026  Lokal tid til filnavn og SFTP mappe
# ═══════════════════════════════════════════════════════════════════════════
"""
TimeLapse Pro — Edge Agent
===========================
Central orchestrator for the edge node. Manages the full lifecycle:

  Bootstrap → Config pull → Schedule capture cycles → Upload → Heartbeat
  → Nightly reboot → Suspend between captures

Entry point: python agent.py [--single-capture] [--debug]

SABSA: Availability  — autonomous operation, survives network outages
       Integrity      — every image hashed and quality-checked
       Accountability — every action logged to DB and headend
       Continuity     — suspend between captures, nightly reboot
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
import paramiko
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

# WebRTC signaling (localhost HTTP client)
try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

# ── Path setup (allows running from any directory) ────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from camera.registry        import get_driver
from diagnostics.camera_diagnostics import collect_camera_diagnostics
from camera.relay           import RelayController
from capture.quality        import QualityChecker
from capture.buffer         import CircularBuffer
from config.manager         import ConfigManager
from diagnostics.collector  import DiagnosticsCollector
from upload.sftp            import UploadManager
from upload.headend_client import HeadendClient
from security               import verify_update_artifact
from update_lifecycle import (
    cleanup_pending_app_update,
    load_pending_app_update,
    mark_pending_app_update_health_confirmed,
    pending_app_update_path,
    release_receipt_matches_artifact,
    restore_previous_app_release,
    write_pending_app_update,
    write_post_restart_guard,
)
try:
    from tunnel.ssh_manager import SshTunnelManager
    _SSH_TUNNEL_AVAILABLE = True
except ImportError:
    _SSH_TUNNEL_AVAILABLE = False
from utils.database         import EdgeDatabase

# Technician authentication (QR code login)
try:
    from technician_auth import TechnicianAuth, get_auth
    from technician_ui   import serve_technician_ui
    _TECH_UI_AVAILABLE = True
except ImportError:
    _TECH_UI_AVAILABLE = False
    TechnicianAuth = None
    serve_technician_ui = None
    get_auth = None

# Frame Push Live View (LAB mode) - F-013C
try:
    from frame_push import start_frame_push, stop_frame_push, is_running as frame_push_is_running
    _FRAME_PUSH_AVAILABLE = True
except ImportError:
    _FRAME_PUSH_AVAILABLE = False
    start_frame_push = None
    stop_frame_push = None
    frame_push_is_running = None

try:
    from service_platform import ServicePlatform
    _SERVICE_PLATFORM_AVAILABLE = True
except ImportError:
    ServicePlatform = None
    _SERVICE_PLATFORM_AVAILABLE = False

# ── HAL (Hardware Abstraction Layer) ──────────────────────────────────────────
try:
    from hal import get_adapter as _hal_get_adapter
    _HAL_ADAPTER = _hal_get_adapter()
except Exception as _hal_exc:
    _HAL_ADAPTER = None
    import logging as _logging
    _logging.getLogger("agent").warning("HAL ikke tilgængeligt: %s", _hal_exc)

# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level  = level,
        format = "%(asctime)s %(levelname)-8s %(name)-30s %(message)s",
        datefmt= "%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            # systemd captures stdout → journalctl -u timelapse-edge
        ]
    )
    # Quiet noisy libraries
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

log = logging.getLogger("agent")


# ── Agent ──────────────────────────────────────────────────────────────────────

class EdgeAgent:
    """
    Main edge agent class.
    Instantiate once and call run() or run_single_capture().
    """

    def __init__(self, config: dict, config_manager: ConfigManager):
        self._cfg        = config
        self._cfg_mgr    = config_manager
        self._device_id  = config["device"]["device_id"]
        self._running    = True

        # Component initialisation
        self._db           = EdgeDatabase(config)
        self._relay        = RelayController(config)        # dual relay (camera + modem)
        self._driver       = get_driver(config)
        self._last_cam_diag: dict = {}
        self._buffer       = CircularBuffer(config)
        self._diag         = DiagnosticsCollector(config)
        self._uploader     = UploadManager(config, self._db)
        self._api          = HeadendClient(config, config_manager)
        self._site_look_config_client = self._init_site_look_config_client()
        self._quality      = QualityChecker(config)
        self._connectivity = self._relay.connectivity      # modem auto-cycle monitor

        # The legacy QR technician server is intentionally opt-in. The TOTP
        # portal is the supported local-management surface; keeping a second
        # unaudited listener on the LAN expands the Edge attack surface.
        self._tech_auth    = None
        self._tech_ui_server = None
        self._legacy_qr_ui_enabled = bool(
            self._cfg.get("technician", {}).get("legacy_qr_ui_enabled", False)
        )
        if _TECH_UI_AVAILABLE and self._legacy_qr_ui_enabled:
            try:
                db_path = self._cfg_mgr.base_dir / "technician_auth.db"
                headend_url = config.get("headend", {}).get("base_url", "http://headend.local:8000")
                self._tech_auth = TechnicianAuth(db_path, self._device_id, headend_url)
                log.info("Technician auth initialised")
            except Exception as exc:
                log.warning("Technician auth init failed: %s", exc)

        # Frame Push Live View (LAB mode)
        self._live_frame_enabled = False
        self._service_platform = ServicePlatform() if _SERVICE_PLATFORM_AVAILABLE else None
        self._lab_service_session = None
        self._register_lab_service_handlers()

        # State
        self._last_heartbeat:    datetime = datetime.min.replace(tzinfo=timezone.utc)
        self._last_config_pull:  datetime = datetime.min.replace(tzinfo=timezone.utc)
        self._last_update_check: datetime = datetime.min.replace(tzinfo=timezone.utc)
        self._last_inventory:    datetime = datetime.min.replace(tzinfo=timezone.utc)
        self._stop_event = threading.Event()
        self._last_siem_emit: dict[str, datetime] = {}
        self._pending_siem_cursor: str | None = None
        self._siem_cursor_path = self._cfg_mgr.base_dir / "siem_journal.cursor"
        self._adaptive_exposure_ev = 0.0
        self._last_capture_skip_until: datetime | None = None

        # Signal handling for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT,  self._handle_signal)

        log.info("EdgeAgent initialised — device_id=%s", self._device_id)

    def _init_site_look_config_client(self):
        """Start the authenticated, offline-capable Site Look policy client."""
        settings = self._cfg.get("site_look_matching", {}) or {}
        if not settings.get("enabled", True):
            log.info("Site Look matching is disabled by Edge configuration")
            return None
        headend_url = self._cfg.get("device", {}).get("headend_url", "")
        if not headend_url or not self._cfg_mgr.api_token:
            log.warning("Site Look matching deferred: Headend URL or Edge credential is missing")
            return None
        try:
            from ai.site_look_config_client import init_config_client

            storage = self._cfg.get("storage", {}) or {}
            client = init_config_client({
                "headend_url": headend_url,
                "edge_node_id": self._device_id,
                "api_token": self._cfg_mgr.api_token,
                "edge_base_dir": str(self._cfg_mgr.base_dir),
                "cache_path": str(Path(storage.get("local_path", "/data/captures")).parent / "site_look_config.json"),
                "poll_interval_seconds": settings.get("config_poll_interval_seconds", 300),
                "cache_ttl_seconds": settings.get("config_cache_ttl_seconds", 86400),
            })
            log.info("Site Look config client initialised")
            return client
        except Exception as exc:
            log.warning("Site Look config client could not start: %s", exc)
            return None

    def _handle_signal(self, signum, frame):
        log.info("Signal %d received — shutting down gracefully…", signum)
        self._running = False
        self._stop_event.set()

    # ── Public entry points ────────────────────────────────────────────────

    def run(self) -> None:
        """Main loop — runs until SIGTERM/SIGINT.
        Checks debug_mode on each iteration and switches to lab loop if enabled.
        """
        log.info("=== TimeLapse Pro Edge Agent starting ===")
        self._startup()

        while self._running:
            try:
                # Re-read schedule each iteration
                self._cfg  = self._cfg_mgr.load()
                schedule   = self._cfg.get("schedule", {})
                mode       = schedule.get("capture_mode", "interval")

                # debug_mode comes from local config (updated by _pull_config every 5 min)
                debug_cfg = self._cfg.get("debug_mode", {})

                if debug_cfg.get("enabled"):
                    self._lab_tick(debug_cfg)
                else:
                    # Reset lab state if switching back to normal
                    if getattr(self, "_lab_relay_on", False):
                        log.info("LAB MODE — exiting, camera release")
                        try:
                            self._driver.disconnect()
                        except Exception as exc:
                            log.warning("LAB MODE — camera disconnect on exit failed: %s", exc)
                        self._camera_power_off("lab exit", force=True)
                        self._lab_relay_on = False
                    self._tick(mode)
            except Exception as exc:
                log.exception("Unhandled error in main loop: %s", exc)
                self._db.log_event(
                    self._device_id, "ERROR", "system",
                    f"Unhandled loop error: {exc}"
                )
                self._stop_event.wait(int(self._cfg.get("system", {}).get("error_recovery_sleep_s", 30)))

        self._shutdown()

    def run_single_capture(self) -> bool:
        """Run exactly one capture cycle — for testing/commissioning."""
        log.info("Single capture mode")
        self._load_camera_features()
        return self._do_capture_cycle()

    # ── Startup ────────────────────────────────────────────────────────────

    def _startup(self) -> None:
        """Perform startup tasks after boot/resume."""
        log.info("Running startup sequence…")

        # 1. Pull fresh config from headend
        self._pull_config()
        self._check_backup_request()

        # 2. Send startup heartbeat
        self._send_heartbeat(check_updates=False)
        self._check_and_apply_updates()

        # CMDB: rapportér hardwareinventar til headend (ikke-blokerende)
        self._report_inventory(force=True)

                # SSH tunnel manager (Sprint C)
        self._tunnel = None
        if _SSH_TUNNEL_AVAILABLE:
            try:
                self._tunnel = SshTunnelManager(self._cfg, self._api)
                self._tunnel.start()
                log.info("SSH tunnel manager initialiseret")
            except Exception as exc:
                log.warning("SSH tunnel manager fejl: %s", exc)

        # Legacy QR UI is opt-in only. Normal local setup uses the hardened
        # TOTP service on 8443, which is started by its own systemd unit.
        if _TECH_UI_AVAILABLE and self._legacy_qr_ui_enabled and self._tech_auth:
            try:
                tech_ui_port = int(self._cfg.get("technician", {}).get("ui_port", 8099))
                self._tech_ui_server = serve_technician_ui(self._tech_auth, port=tech_ui_port)
                if self._tech_ui_server:
                    log.info("Technician UI started on port %d", tech_ui_port)
            except Exception as exc:
                log.warning("Technician UI start failed: %s", exc)
        elif _TECH_UI_AVAILABLE:
            log.info("Legacy QR technician UI disabled; use local TOTP management on port 8443")

        # 3. Detect camera features (once per session)
        self._load_camera_features()

        # 3b. Auto-bootstrap sibling kameraer
        self._auto_bootstrap_cameras()

        # 4. Retry any pending uploads from before last reboot
        camera_id = self._cfg.get("device", {}).get("device_id", "unknown")
        allowed, wait_s, _remaining_s = self._upload_slot_state()
        if allowed:
            api_retried = self._retry_pending_api_uploads()
            if api_retried:
                log.info("Startup API upload retry: %d", api_retried)
            retry_results = self._uploader.retry_pending(camera_id)
            if any(v > 0 for v in retry_results.values()):
                log.info("Startup SFTP upload retry: %s", retry_results)
        else:
            log.info("Startup upload retry deferred by Headend slot: next_slot_in_s=%s", wait_s)

        # 5. Sync unsynced capture records to headend
        self._sync_captures()

        # 6. A candidate app release is not deployed until this complete
        # startup sequence has succeeded.  The independent systemd guard keeps
        # the previous release recoverable if the new agent never reaches here.
        self._finalize_pending_app_update_health()

    def _auto_bootstrap_cameras(self) -> None:
        node_cameras = self._cfg.get('node_cameras', [])
        multi_mode   = self._cfg.get('multi_camera_mode', 'single')
        if not node_cameras or multi_mode != 'auto_bootstrap':
            return
        log.info("Auto-bootstrap: %d sibling kameraer", len(node_cameras))
        for cam in node_cameras:
            try:
                self._api._post(f"/node/{self._device_id}/bootstrap-camera", cam)
                log.info("Bootstrapped: %s-%d", self._device_id, cam.get('camera_index', 1))
            except Exception as exc:
                log.warning("Bootstrap fejl: %s", exc)

    def _discover_cameras(self) -> list:
        """Find kameraer via stabile udev symlinks /dev/timelapse-camN.

        Symlinks konfigureres i /etc/udev/rules.d/99-timelapse-cameras.rules
        baseret på fysisk USB port (ID_PATH_TAG) — stabile ved relay power cycle.
        """
        import os

        node_cameras   = self._cfg.get('node_cameras', [])
        primary_serial = self._cfg.get('camera', {}).get('serial_number', '')
        primary_gpio   = self._cfg.get('camera', {}).get('relay_gpio_pin', 356)

        # Byg liste af konfigurerede kameraer
        cam_configs = [
            {'device_id': self._device_id, 'relay_gpio': primary_gpio,
             'serial': primary_serial, 'symlink': '/dev/timelapse-cam0'},
        ]
        for nc in node_cameras:
            idx = nc.get('camera_index', 1)
            cam_configs.append({
                'device_id':  f"{self._device_id}-{idx}",
                'relay_gpio': nc.get('relay_gpio_camera', 357),
                'serial':     nc.get('serial_number', ''),
                'symlink':    f'/dev/timelapse-cam{idx}',
            })

        detected = []
        for cc in cam_configs:
            symlink = cc['symlink']
            if not os.path.exists(symlink):
                log.warning("Symlink mangler: %s — kamera ikke tilsluttet?", symlink)
                continue
            try:
                real  = os.path.realpath(symlink)   # fx /dev/bus/usb/005/035
                parts = real.split('/')
                port  = f"usb:{parts[-2]},{parts[-1]}"
            except Exception as exc:
                log.warning("Symlink resolve fejl %s: %s", symlink, exc)
                continue
            log.info("Kamera: %s → %s (device=%s gpio=%d)",
                     symlink, port, cc['device_id'], cc['relay_gpio'])
            detected.append({
                'device_id':  cc['device_id'],
                'relay_gpio': cc['relay_gpio'],
                'port':       port,
                'symlink':    symlink,
            })

        log.info("Klar til burst: %d kameraer %s",
                 len(detected), [c['device_id'] for c in detected])
        return detected

    def _camera_power_mode(self) -> str:
        mode = str(self._cfg.get("camera", {}).get("power_mode", "relay")).strip().lower()
        aliases = {
            "relay_controlled": "relay",
            "relay-controlled": "relay",
            "usb": "usb_powered",
            "usb-powered": "usb_powered",
            "constant_usb": "usb_powered",
            "always_on": "usb_powered",
            "no_relay": "usb_powered",
            "none": "usb_powered",
        }
        return aliases.get(mode, mode)

    def _camera_uses_relay(self) -> bool:
        return self._camera_power_mode() == "relay"

    def _camera_warmup_seconds(self) -> int:
        if not self._camera_uses_relay():
            return 0
        return int(self._cfg.get("camera", {}).get("relay_on_seconds_before", 10))

    def _camera_settle_seconds(self) -> int:
        if not self._camera_uses_relay():
            return 0
        return int(self._cfg.get("camera", {}).get("relay_off_seconds_after", 5))

    def _camera_power_on(self, reason: str = "") -> None:
        if self._camera_uses_relay():
            self._relay.camera.power_on()
            return
        detail = f" ({reason})" if reason else ""
        log.info("Camera power mode=%s — relay power_on skipped%s", self._camera_power_mode(), detail)

    def _camera_power_off(self, reason: str = "", force: bool = False) -> None:
        if self._camera_uses_relay():
            if force:
                self._relay.camera.force_off()
            else:
                self._relay.camera.power_off()
            return
        detail = f" ({reason})" if reason else ""
        log.info("Camera power mode=%s — relay power_off skipped%s", self._camera_power_mode(), detail)

    def _register_lab_service_handlers(self) -> None:
        if not getattr(self, "_service_platform", None):
            return

        def power_acquire(_platform, _session, _kwargs):
            if not getattr(self, "_lab_relay_on", False):
                self._camera_power_on("lab service operation")
                self._lab_relay_on = True
                warmup_s = self._camera_warmup_seconds()
                if warmup_s:
                    time.sleep(warmup_s)
            return {"ok": True, "camera_relay_on": True}

        def power_release(_platform, _session, _kwargs):
            self._camera_power_off("lab service operation", force=True)
            self._lab_relay_on = False
            return {"ok": True, "camera_relay_on": False}

        def power_cycle(platform, session, kwargs):
            power_release(platform, session, kwargs)
            time.sleep(5)
            return power_acquire(platform, session, kwargs)

        def cleanup_camera(_platform, _session, reason):
            try:
                self._driver.disconnect()
            except Exception:
                pass
            self._camera_power_off(reason, force=True)
            self._lab_relay_on = False

        self._service_platform.register_handler("camera.power.acquire", power_acquire)
        self._service_platform.register_handler("camera.power.release", power_release)
        self._service_platform.register_handler("camera.power.cycle", power_cycle)
        self._service_platform.register_cleanup_handler("CameraPowerLease", cleanup_camera)

    def _emit_siem_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        *,
        source: str = "edge-agent",
        details: dict | None = None,
        min_interval_s: int = 3600,
    ) -> None:
        """Post a rate-limited SIEM event to Headend; Headend handles email notification."""
        now = datetime.now(timezone.utc)
        key = f"{event_type}:{severity}:{message[:120]}"
        last = self._last_siem_emit.get(key)
        if last and (now - last).total_seconds() < min_interval_s:
            return
        self._last_siem_emit[key] = now
        raw = message
        if details:
            raw = f"{message} | details={details}"
        try:
            self._api._post(f"/siem/events/{self._device_id}", {
                "events": [{
                    "event_type": event_type,
                    "severity": severity.upper(),
                    "username": None,
                    "source_ip": None,
                    "raw_message": raw,
                    "occurred_at": now.isoformat(),
                    "source": source,
                }]
            })
        except Exception as exc:
            log.debug("SIEM emit failed for %s: %s", event_type, exc)

    def _siem_cfg(self) -> dict:
        cfg = dict(self._cfg.get("siem", {}))
        mode = str(cfg.get("mode", "prod")).lower()
        cfg.setdefault("enabled", True)
        cfg.setdefault("mode", mode)
        cfg.setdefault("forward_interval_s", 300)
        cfg.setdefault("max_events_per_batch", 200 if mode == "lab" else 50)
        cfg.setdefault("journal_units", ["timelapse-edge.service"])
        cfg.setdefault("min_severity", "info" if mode == "lab" else "warning")
        return cfg

    @staticmethod
    def _severity_rank(level: str) -> int:
        return {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}.get(level.lower(), 1)

    @staticmethod
    def _journal_priority_to_severity(priority: str | int | None) -> str:
        try:
            p = int(priority)
        except Exception:
            return "info"
        if p <= 2:
            return "critical"
        if p == 3:
            return "error"
        if p == 4:
            return "warning"
        return "info"

    @staticmethod
    def _parse_python_log_message(message: str) -> tuple[str | None, str | None]:
        match = re.match(
            r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+([A-Z]+)\s+([^\s]+)\s+(.*)$",
            message or "",
        )
        if not match:
            return None, message
        return match.group(2), match.group(3)

    def _collect_siem_events_for_sync(self) -> list[dict]:
        """Collect pending SIEM journal events for the consolidated sync poll.

        Split out of the old, independently-timed _forward_siem_logs() so SIEM
        forwarding rides on the same single request as config/heartbeat/updates
        instead of its own separate 5-minute POST. See _run_sync() and
        Dokumentation/HANDOVER_LOG.md 2026-08-19.

        The journal cursor advances immediately when there's nothing to send
        (avoids re-reading the same empty window every cycle). When there IS
        something to send, the cursor only advances once the sync poll actually
        succeeds — _run_sync() calls _persist_siem_cursor_after_sync() for that,
        matching the original per-call "only advance on confirmed send" semantics.
        """
        cfg = self._siem_cfg()
        if not cfg.get("enabled", True):
            return []

        min_sev = str(cfg.get("min_severity", "warning")).lower()
        max_events = max(1, int(cfg.get("max_events_per_batch", 100)))
        units = cfg.get("journal_units") or ["timelapse-edge.service"]

        cmd = ["journalctl", "--no-pager", "-o", "json", "--show-cursor"]
        cursor = None
        try:
            if self._siem_cursor_path.exists():
                cursor = self._siem_cursor_path.read_text().strip()
        except Exception:
            cursor = None
        if cursor:
            cmd += ["--after-cursor", cursor]
        else:
            since_s = int(cfg.get("initial_since_minutes", 10))
            cmd += ["--since", f"{since_s} minutes ago"]
        for unit in units:
            cmd += ["-u", str(unit)]
        cmd += ["-n", str(max_events)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        except Exception as exc:
            log.debug("SIEM journal read failed: %s", exc)
            return []
        if result.returncode != 0:
            log.debug("SIEM journal read rc=%s stderr=%s", result.returncode, result.stderr[:200])
            return []

        now = datetime.now(timezone.utc)
        events: list[dict] = []
        latest_cursor = cursor
        for line in result.stdout.splitlines():
            if line.startswith("-- cursor:"):
                latest_cursor = line.split(":", 1)[1].strip()
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            latest_cursor = row.get("__CURSOR") or latest_cursor
            message = row.get("MESSAGE", "")
            if not message or "/siem/events/" in message or "SIEM journal" in message:
                continue
            severity = self._journal_priority_to_severity(row.get("PRIORITY"))
            logger_name, clean_message = self._parse_python_log_message(message)
            if logger_name:
                level_match = re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+([A-Z]+)", message)
                if level_match:
                    severity = level_match.group(1).lower()
                    if severity == "warn":
                        severity = "warning"
            if self._severity_rank(severity) < self._severity_rank(min_sev):
                continue
            ts_raw = row.get("__REALTIME_TIMESTAMP")
            occurred = now
            try:
                occurred = datetime.fromtimestamp(int(ts_raw) / 1_000_000, tz=timezone.utc)
            except Exception:
                pass
            events.append({
                "event_type": "log",
                "severity": severity,
                "category": "edge_journal",
                "source": "edge_journal",
                "logger": logger_name,
                "process": row.get("SYSLOG_IDENTIFIER") or row.get("_COMM"),
                "raw_message": clean_message or message,
                "occurred_at": occurred.isoformat(),
            })

        self._pending_siem_cursor = None
        if not events:
            # Nothing to send — advance the cursor now, no network call needed.
            if latest_cursor and latest_cursor != cursor:
                try:
                    self._siem_cursor_path.write_text(latest_cursor)
                except Exception:
                    pass
            return []
        # Cursor only advances once the sync poll that carries these events
        # actually succeeds — see _persist_siem_cursor_after_sync().
        self._pending_siem_cursor = latest_cursor
        return events

    def _persist_siem_cursor_after_sync(self) -> None:
        """Advance the SIEM journal cursor once a sync poll carrying pending
        events has actually been confirmed delivered. No-op when the last
        collected batch was empty (cursor was already advanced inline)."""
        cursor = self._pending_siem_cursor
        self._pending_siem_cursor = None
        if not cursor:
            return
        try:
            self._siem_cursor_path.write_text(cursor)
        except Exception:
            pass

    def _check_camera_profile_known(self, context: str) -> None:
        if not hasattr(self._driver, "get_profile_summary"):
            return
        try:
            profile = self._driver.get_profile_summary()
        except Exception:
            return
        if profile.get("profile_key") == "default":
            model = profile.get("detected_model", "Unknown")
            if model and model != "Unknown":
                self._emit_siem_event(
                    "camera_profile_missing",
                    "CRITICAL",
                    f"Camera '{model}' detected without a specific TimeLapse Pro camera profile",
                    details={"model": model, "context": context, "profile": profile},
                    min_interval_s=86400,
                )

    def _capture_single_camera(self, cam, dest_dir, results, idx):
        from camera.registry import get_driver as _get_driver
        device_id = cam['device_id']
        log.info("Thread %s port %s", device_id, cam['port'])
        cam_cfg = dict(self._cfg)
        cam_cfg['camera'] = dict(self._cfg.get('camera', {}))
        cam_cfg['camera']['gphoto2_port'] = cam['port']
        cam_cfg['device'] = dict(self._cfg.get('device', {}))
        cam_cfg['device']['device_id'] = device_id
        try:
            driver = _get_driver(cam_cfg)
            driver.connect()
            commands = self._build_camera_commands()
            if commands:
                driver.apply_initial_commands(commands)
            result = driver.capture_image(dest_dir)
            driver.disconnect()
            quality_report = self._quality_report(result.filepath, result.sha256)
            self._write_qa_sidecar(result.filepath, quality_report)
            capture_id = self._db.insert_capture(
                device_id=device_id, filepath=result.filepath,
                sha256=result.sha256, captured_at=result.timestamp,
                camera_model=result.camera_model, driver_name=result.driver_name,
                filesize=result.filesize, exposure_time=result.exposure_time,
                aperture=result.aperture, iso=result.iso, focus_mode=result.focus_mode,
                quality_flag=quality_report.get("flag"), quality_passed=bool(quality_report.get("passed")),
                blur_score=quality_report.get("blur_score"), brightness=quality_report.get("brightness_mean"),
            )
            upload = self._upload_capture_transports(capture_id, result.filepath, device_id)
            results[idx] = {'success': True, 'device_id': device_id, 'upload': upload}
        except Exception as exc:
            log.error("Thread %s fejl: %s", device_id, exc)
            results[idx] = {'success': False, 'device_id': device_id, 'error': str(exc)}

    def _do_multi_capture_cycle(self, cameras) -> bool:
        log.info("Multi-burst: %d kameraer", len(cameras))
        relay_gpios = [c['relay_gpio'] for c in cameras]
        for gpio in relay_gpios:
            try: open(f'/sys/class/gpio/gpio{gpio}/value', 'w').write('0')
            except Exception as exc: log.warning("GPIO %d ON: %s", gpio, exc)
        warmup_s = int(self._cfg.get('camera', {}).get('relay_on_seconds_before', 10))
        log.info("Warmup %ds…", warmup_s)
        time.sleep(warmup_s)
        dest_dir = self._buffer.path
        results  = [None] * len(cameras)
        threads  = [threading.Thread(target=self._capture_single_camera,
            args=(cam, dest_dir, results, idx), daemon=True)
            for idx, cam in enumerate(cameras)]
        log.info("Start %d threads simultant…", len(threads))
        for t in threads: t.start()
        for t in threads: t.join(timeout=120)
        settle_s = int(self._cfg.get('camera', {}).get('relay_off_seconds_after', 5))
        time.sleep(settle_s)
        for gpio in relay_gpios:
            try: open(f'/sys/class/gpio/gpio{gpio}/value', 'w').write('1')
            except Exception as exc: log.warning("GPIO %d OFF: %s", gpio, exc)
        ok  = sum(1 for r in results if r and r.get('success'))
        err = sum(1 for r in results if r and not r.get('success'))
        log.info("Burst: %d OK, %d fejl", ok, err)
        self._sync_captures()
        return ok > 0

    def _load_camera_features(self) -> None:
        """Detect camera capabilities for this session."""
        try:
            self._camera_power_on("feature detection")
            self._driver.connect()
            self._check_camera_profile_known("feature_detection")
            self._has_autofocus = self._driver.supports_autofocus()
            self._has_refocus   = self._driver.supports_remote_focus()
            self._driver.disconnect()
            self._camera_power_off("feature detection")
            log.info(
                "Camera features: autofocus=%s remote_focus=%s",
                self._has_autofocus, self._has_refocus
            )
        except Exception as exc:
            log.warning("Could not detect camera features: %s", exc)
            self._emit_siem_event(
                "camera_detection_failed",
                "ERROR",
                f"Could not detect camera features: {exc}",
                details={"context": "feature_detection", "power_mode": self._camera_power_mode()},
            )
            self._has_autofocus = False
            self._has_refocus   = False

    # ── Main tick ──────────────────────────────────────────────────────────

    def _tick(self, mode: str) -> None:
        """
        One iteration of the main loop:
          - Check if it's time to capture
          - If yes: do capture cycle
          - Check if heartbeat is due
          - Sleep or suspend until next event
        """
        now = datetime.now(timezone.utc)

        # Consolidated sync poll: one request carries diagnostics/app_version/
        # SIEM events out and config/pending-updates back, replacing what used
        # to be three independently-timed loops (config-pull, heartbeat,
        # SIEM-forward) plus a redundant nested update-check timer. Interval is
        # configurable (diagnostics.sync_poll_interval_minutes) so operators can
        # tune responsiveness vs. communication overhead per device. See
        # Dokumentation/HANDOVER_LOG.md 2026-08-19.
        sync_interval = timedelta(minutes=int(
            self._cfg.get("diagnostics", {}).get("sync_poll_interval_minutes", 5)
        ))
        if now - self._last_heartbeat > sync_interval:
            self._run_sync()
            self._sync_captures()
            self._check_backup_request()
            # Tjek om headend har bedt om en opdatering (legacy LAB-path)
            self._check_update()

        # Check capture schedule by scheduled slot, not by current wall-clock cycle.
        capture_slot = self._scheduled_capture_slot(now, mode)
        if capture_slot:
            slot_id = capture_slot["slot_id"]
            if not self._db.claim_capture_slot(
                slot_id=slot_id,
                device_id=self._device_id,
                mode=mode,
                scheduled_at=capture_slot["scheduled_at"],
            ):
                log.debug("Capture slot already attempted: %s", slot_id)
            else:
                self._run_capture_slot(now, mode, capture_slot)

        # Upload pending large files only inside the Headend-assigned slot.
        # This runs after capture checks so upload backlog cannot delay capture.
        self._retry_pending_uploads_if_slot()

        # Calculate sleep until next event
        sleep_s = self._seconds_until_next_event(now, mode)

        if sleep_s > 60:
            log.info("Sleeping %ds until next capture…", sleep_s)
        # Smart wake-up: use max_idle_sleep_s to reduce unnecessary wake-ups
        # Default 300s (5 min) - configurable via system.max_idle_sleep_s
        max_idle_sleep = int(self._cfg.get("system", {}).get("max_idle_sleep_s", 300))
        self._stop_event.wait(min(sleep_s, max_idle_sleep))  # wake at least every max_idle_sleep_s

    def _run_capture_slot(self, now: datetime, mode: str, capture_slot: dict) -> None:
        slot_id = capture_slot["slot_id"]
        try:
            suppressed = self._capture_suppressed_by_headend_signal(now)
            if suppressed:
                log.info("Capture udsat/sprunget over: %s", suppressed)
                self._db.log_event(self._device_id, "INFO", "capture", f"Capture suppressed: {suppressed}")
                self._db.complete_capture_slot(slot_id=slot_id, status="skipped", result=suppressed)
                return
            else:
                # 2026-07-04 (Peter): læs GPS HER, lige før relæet tænder --
                # ikke løbende under idle-ventetiden. Relæet dræber fix'et
                # med det samme, og der går lang tid efter relæet slukkes
                # før et fix er tilbage. `_should_capture()` returnerer True
                # `lead_s` (~13s) sekunder før relæet rent faktisk tænder
                # (se _camera_warmup_seconds/_do_capture_cycle), så dette er
                # det sidste og bedste tidspunkt at læse på — maksimal tid
                # siden sidste relæ-slukning er gået, og GPS'en har haft
                # bedst mulig chance for at nå et fix, inden relæet dræber
                # det igen om et øjeblik.
                try:
                    if hasattr(self._driver, "refresh_gps_cache"):
                        self._driver.refresh_gps_cache()
                except Exception as _gps_exc:
                    log.debug("GPS-cache opdatering sprunget over: %s", _gps_exc)

                node_cameras = self._cfg.get('node_cameras', [])
                multi_mode   = self._cfg.get('multi_camera_mode', 'single')
                if node_cameras and multi_mode in ('auto_bootstrap', 'manual'):
                    cameras = self._discover_cameras()
                    if len(cameras) > 1:
                        ok = self._do_multi_capture_cycle(cameras)
                    else:
                        log.info("Kun %d kamera fundet — single mode", len(cameras))
                        ok = self._do_capture_cycle()
                else:
                    ok = self._do_capture_cycle()
                capture_id = (getattr(self, "_last_capture_result", None) or {}).get("capture_id")
                self._db.complete_capture_slot(
                    slot_id=slot_id,
                    status="success" if ok else "failed",
                    capture_id=capture_id,
                    result="capture_cycle",
                )
        except Exception as exc:
            self._db.complete_capture_slot(slot_id=slot_id, status="failed", error=str(exc))
            raise

    # ── Capture cycle ───────────────────────────────────────────────────────

    def _do_capture_cycle(self) -> bool:
        """
        Full capture cycle:
          Power on → Connect → Configure → Capture → Quality check
          → Store → Upload → Power off

        Returns True on success, False on failure.
        """
        log.info("─── Starting capture cycle ───")
        success = False
        self._last_capture_result = None

        try:
            # 1. Power camera on and connect
            self._camera_power_on("capture cycle")
            try:
                self._driver.connect()
                self._check_camera_profile_known("capture_cycle")
            except Exception as exc:
                log.error("Camera connect failed: %s", exc)
                self._emit_siem_event(
                    "camera_detection_failed",
                    "ERROR",
                    f"Camera connect failed: {exc}",
                    details={"context": "capture_cycle", "power_mode": self._camera_power_mode()},
                )
                self._db.log_event(
                    self._device_id, "ERROR", "camera",
                    f"Camera connect failed: {exc}"
                )
                return False

            # 2. Apply configuration commands
            #    Byg commands fra camera config_overrides (hierarkisk model)
            #    Override erstatter initial_commands for de parametre der er sat
            commands = self._build_camera_commands()
            if commands:
                log.info("Applying %d camera commands", len(commands))
                failed = self._driver.apply_initial_commands(commands)
                if failed:
                    log.warning("Some camera commands failed: %s", failed)
                else:
                    log.info("Camera commands applied OK")

            # 3. Health check before capture
            if not self._driver.health_check():
                log.error("Camera health check failed — aborting capture")
                self._db.log_event(
                    self._device_id, "ERROR", "camera",
                    "Health check failed before capture"
                )
                return False

            # 4. Capture image — wait for precise moment if fixed mode
            schedule = self._cfg.get("schedule", {})
            if schedule.get("capture_mode") == "fixed":
                from zoneinfo import ZoneInfo
                import time as _time
                tz_name   = schedule.get("timezone", "UTC")
                tz        = ZoneInfo(tz_name)
                now_local = datetime.now(tz)
                for t_str in schedule.get("capture_times", []):
                    try:
                        h, m   = map(int, t_str.split(":"))
                        target = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
                        diff   = (target - now_local).total_seconds()
                        if -5 < diff < 30:
                            if diff > 0:
                                log.info("Precise wait %.2fs before trigger at %s", diff, t_str)
                                _time.sleep(diff)
                            break
                    except Exception:
                        pass
            dest_dir = self._buffer.path
            try:
                result = self._driver.capture_image(dest_dir)
            except Exception as exc:
                log.error("Capture failed: %s", exc)
                self._db.log_event(
                    self._device_id, "ERROR", "capture", f"Capture error: {exc}"
                )
                return False

            log.info(
                "Captured: %s (%.1f MB) sha256=%s…",
                result.filepath.name,
                result.filesize / 1e6,
                result.sha256[:12]
            )

            # 5. Quality check
            quality_report = self._quality_report(result.filepath, None)  # sha256 pre-XMP — skip disk re-verify
            self._write_qa_sidecar(result.filepath, quality_report)
            if not quality_report.get("passed"):
                log.warning("Quality FAILED: %s — %s", result.filepath.name, quality_report.get("message"))
            else:
                log.info("Quality OK: %s", quality_report.get("message"))
            self._maybe_update_adaptive_exposure(quality_report)

            # 6. Store in DB
            capture_id = self._db.insert_capture(
                device_id    = self._device_id,
                filepath     = result.filepath,
                sha256       = result.sha256,
                captured_at  = result.timestamp,
                camera_model = result.camera_model,
                driver_name  = result.driver_name,
                filesize     = result.filesize,
                exposure_time= result.exposure_time,
                aperture     = result.aperture,
                iso          = result.iso,
                focus_mode   = result.focus_mode,
                quality_flag = quality_report.get("flag"),
                quality_passed=bool(quality_report.get("passed")),
                blur_score   = quality_report.get("blur_score"),
                brightness   = quality_report.get("brightness_mean"),
            )

            # 7. Enforce circular buffer BEFORE upload (free space first)
            self._buffer.enforce(self._db)

            # 8. Upload — report connectivity result. Capture timing is not
            # delayed by upload slots; files are queued locally if outside slot.
            camera_id      = self._cfg.get("device", {}).get("device_id", "unknown")
            upload_results = self._upload_capture_transports(capture_id, result.filepath, camera_id)
            log.info("Upload results: %s", upload_results)
            self._last_capture_result = {
                "capture_id": capture_id,
                "filename": result.filepath.name,
                "filepath": str(result.filepath),
                "filesize": result.filesize,
                "sha256": result.sha256,
                "quality": quality_report,
                "uploaded": bool(upload_results.get("primary")),
            }

            if upload_results.get("primary"):
                self._connectivity.report_success()
            else:
                self._connectivity.report_failure()

            # Camera diagnostics while the camera is still awake
            # Disconnect driver first to free gphoto2 USB connection
            try:
                self._driver.disconnect()
            except Exception:
                pass
            try:
                cam_model = self._cfg.get("camera", {}).get("model", "")
                # Byg expected_config fra den hierarkiske command liste
                # så drift-check sammenligner med den faktiske config vi sætter
                expected: dict[str, str] = {}
                for cmd in self._build_camera_commands():
                    if "=" in cmd:
                        k, v = cmd.split("=", 1)
                        expected[k.strip()] = v.strip()
                # Settings the active camera profile marks non-enforceable
                # (e.g. readonly on this body, like Nikon Z30 focus mode) —
                # never flag these as drift, see R14 / camera_diagnostics.py.
                non_enforceable: set[str] = set()
                try:
                    if hasattr(self._driver, "get_profile_summary"):
                        profile_summary = self._driver.get_profile_summary()
                        for cfg_key, spec in (profile_summary.get("config_commands") or {}).items():
                            if isinstance(spec, dict) and spec.get("skip"):
                                non_enforceable.add(cfg_key)
                except Exception:
                    non_enforceable = set()
                self._last_cam_diag = collect_camera_diagnostics(
                    cam_model,
                    expected,
                    non_enforceable_keys=non_enforceable,
                    include_fleet_defaults=not bool(
                        (self._cfg.get("camera_profile", {}) or {}).get("profile_key")
                    ),
                )
                log.info("Camera diagnostics collected: battery=%s shutter=%s drift=%s",
                    self._last_cam_diag.get("camera_status", {}).get("battery_pct"),
                    self._last_cam_diag.get("camera_status", {}).get("shutter_count"),
                    len(self._last_cam_diag.get("camera_config_drift", [])))
                if self._last_cam_diag.get("camera_config_drift"):
                    log.warning("Camera config drift: %s",
                        [d["param"] for d in self._last_cam_diag["camera_config_drift"]])
                if self._last_cam_diag.get("shutter_alarm"):
                    log.warning("Shutter alarm: %.1f%% of rated life",
                        self._last_cam_diag["shutter_pct"])
            except Exception as cam_exc:
                log.warning("Camera diagnostics failed: %s", cam_exc)

            # Fresh camera diagnostics ride along on the next consolidated
            # sync poll (_run_sync picks up self._last_cam_diag) instead of
            # triggering their own separate heartbeat round-trip here.
            self._sync_captures()
            success = True

        except Exception as exc:
            log.exception("Unexpected error in capture cycle: %s", exc)
            self._db.log_event(
                self._device_id, "ERROR", "capture",
                f"Unexpected capture cycle error: {exc}"
            )
        finally:
            # Always disconnect and power off, even on error
            try:
                self._driver.disconnect()
            except Exception:
                pass
            self._camera_power_off("capture cycle")

        log.info("─── Capture cycle complete (success=%s) ───", success)
        return success

    # ── Scheduling ──────────────────────────────────────────────────────────

    def _should_capture(self, now: datetime, mode: str) -> bool:
        """Return True if relay should power ON now (warmup-adjusted)."""
        return self._scheduled_capture_slot(now, mode) is not None

    def _scheduled_capture_slot(self, now: datetime, mode: str) -> dict | None:
        """Return the planned capture slot due now, including lead-window and catch-up."""
        schedule = self._cfg.get("schedule", {})
        warmup_s = self._camera_warmup_seconds()
        lead_s   = warmup_s + 3
        catchup_s = int(schedule.get("capture_catchup_seconds", max(60, lead_s + 60)))
        active_hours = schedule.get("active_hours")
        if active_hours and len(active_hours) == 2:
            tz_name   = schedule.get("timezone", "UTC")
            local_now = self._to_local(now, tz_name)
            start_t   = self._parse_time(active_hours[0])
            end_t     = self._parse_time(active_hours[1])
            if not (start_t <= local_now.time() <= end_t):
                return None
        if mode == "interval":
            interval_s   = int(schedule.get("interval_minutes", 60)) * 60
            epoch_s      = int(now.timestamp())
            pos_in_cycle = epoch_s % interval_s
            if (interval_s - pos_in_cycle) <= lead_s:
                scheduled_at = datetime.fromtimestamp(epoch_s - pos_in_cycle + interval_s, timezone.utc)
                return self._slot_payload("interval", scheduled_at)
            if 0 <= pos_in_cycle <= catchup_s:
                scheduled_at = datetime.fromtimestamp(epoch_s - pos_in_cycle, timezone.utc)
                return self._slot_payload("interval", scheduled_at)
            return None
        if mode == "fixed":
            tz_name   = schedule.get("timezone", "UTC")
            local_now = self._to_local(now, tz_name)
            for t_str in schedule.get("capture_times", []):
                try:
                    h, m   = map(int, t_str.split(":"))
                    target = local_now.replace(hour=h, minute=m, second=0, microsecond=0)
                    diff   = (target - local_now).total_seconds()
                    if -catchup_s <= diff <= lead_s:
                        return self._slot_payload("fixed", target.astimezone(timezone.utc))
                except Exception:
                    pass
        return None

    def _slot_payload(self, mode: str, scheduled_at: datetime) -> dict:
        scheduled_utc = scheduled_at.astimezone(timezone.utc).replace(microsecond=0)
        return {
            "slot_id": f"{self._device_id}:{mode}:{scheduled_utc.isoformat()}",
            "scheduled_at": scheduled_utc,
            "mode": mode,
        }

    def _capture_suppressed_by_headend_signal(self, now: datetime) -> str | None:
        """Return a reason if Headend asked Edge to avoid captures right now."""
        schedule = self._cfg.get("schedule", {})
        windows = (
            schedule.get("capture_avoid_windows")
            or schedule.get("solar_reflection_avoid_windows")
            or []
        )
        if not windows:
            return None
        tz_name = schedule.get("timezone", "UTC")
        local_now = self._to_local(now, tz_name)
        for window in windows:
            if not isinstance(window, dict):
                continue
            try:
                start = self._parse_time(str(window.get("start", "")))
                end = self._parse_time(str(window.get("end", "")))
            except Exception:
                continue
            in_window = start <= local_now.time() <= end if start <= end else (
                local_now.time() >= start or local_now.time() <= end
            )
            if not in_window:
                continue
            action = str(window.get("action", "skip")).lower()
            reason = str(window.get("reason", "headend_avoid_window"))
            if action in {"skip", "delay", "avoid"}:
                return f"{reason} ({window.get('start')}–{window.get('end')})"
        return None

    def _seconds_until_next_event(self, now: datetime, mode: str) -> int:
        """Calculate seconds until next capture or heartbeat."""
        schedule      = self._cfg.get("schedule", {})
        warmup_s      = self._camera_warmup_seconds()
        lead_s        = warmup_s + 3
        heartbeat_min = int(self._cfg.get("diagnostics", {}).get("sync_poll_interval_minutes", 5))
        if mode == "interval":
            interval_s   = int(schedule.get("interval_minutes", 60)) * 60
            epoch_s      = int(now.timestamp())
            pos_in_cycle = epoch_s % interval_s
            until_capture = max(1, interval_s - pos_in_cycle - lead_s)
        elif mode == "fixed":
            tz_name   = schedule.get("timezone", "UTC")
            local_now = self._to_local(now, tz_name)
            min_secs  = 3600
            for t_str in schedule.get("capture_times", []):
                try:
                    h, m   = map(int, t_str.split(":"))
                    target = local_now.replace(hour=h, minute=m, second=0, microsecond=0)
                    diff   = (target - local_now).total_seconds() - lead_s
                    if diff < 0:
                        diff += 86400
                    min_secs = min(min_secs, diff)
                except Exception:
                    pass
            until_capture = max(1, int(min_secs))
        else:
            until_capture = int(self._cfg.get("system", {}).get("min_sleep_s", 60))
        elapsed_heartbeat = (now - self._last_heartbeat).total_seconds()
        until_heartbeat   = max(1, heartbeat_min * 60 - elapsed_heartbeat)
        return int(min(until_capture, until_heartbeat))

    def _update_poll_interval(self) -> timedelta:
        minutes = int(
            self._cfg.get("diagnostics", {}).get("update_poll_interval_minutes", 5)
        )
        return timedelta(minutes=max(1, minutes))

    def _check_and_apply_updates_if_due(self) -> None:
        if not self._running or self._stop_event.is_set():
            return
        if datetime.now(timezone.utc) - self._last_update_check < self._update_poll_interval():
            return
        self._check_and_apply_updates()

    # ── Headend communication ───────────────────────────────────────────────

    def _pull_config(self) -> None:
        """Fetch and apply updated config from headend."""
        ok, data = self._api.fetch_config()
        if ok and data:
            self._apply_fetched_config(data)
        else:
            log.info("Config pull failed — using cached config")
        self._last_config_pull = datetime.now(timezone.utc)

    def _apply_fetched_config(self, data: dict) -> None:
        """Apply an already-fetched config response. Split out of
        _pull_config() so the consolidated sync poll (_run_sync) can apply a
        config it received inline, without a second /config round-trip.
        """
        old_version = self._cfg.get("config_version", "")
        try:
            self._api.ensure_signing_enrolled(data.get("security", {}))
            new_version = data.get("config_version", "")
            self._cfg_mgr.save_config(data)
            self._cfg = self._cfg_mgr.load()
            self._uploader.update_config(data)

            if new_version != old_version:
                log.info("Config version ændret %s→%s — anvender live", old_version[:8], new_version[:8])
                self._apply_config_changes(data)
            else:
                log.debug("Config uændret — ingen live apply nødvendig")
        except Exception as exc:
            log.warning("Could not apply headend config: %s", exc)

        # BT-TOTP secret (lokal Servicetekniker-adgang) — SEC-016-BOOTSTRAP-GAP.
        # Deliberately OUTSIDE the config_version gate above: that gate is a
        # legitimate optimization for expensive/disruptive changes, but wrong
        # here. sync_bt_totp_config() is cheap and idempotent — a file read
        # plus string compare when nothing changed — so it runs on every poll.
        # A device whose cached config_version already equals Headend's current
        # hash (e.g. because a prior poll's version write succeeded while this
        # write didn't) would otherwise never get another chance to converge;
        # the version compare keeps matching forever while the file stays wrong.
        try:
            self._sync_bt_totp_config(data.get("bt_totp", {}))
        except Exception as exc:
            log.warning("BT-TOTP auto-sync fejl: %s", exc)

    def _check_backup_request(self) -> None:
        """Run a Headend-requested Edge backup once."""
        backup_requested = self._cfg.get("backup_requested") is True
        requested_at = str(self._cfg.get("backup_requested_at") or "")
        if not backup_requested:
            return
        marker = self._cfg_mgr.base_dir / ".last_backup_request"
        if requested_at and marker.exists() and marker.read_text().strip() == requested_at:
            return
        try:
            archive, sha256, size_kb = self._create_edge_backup_archive(requested_at)
            ok, result = self._api.upload_edge_backup(archive, sha256)
            if ok:
                log.info("Edge backup upload OK: %s (%d KB)", archive.name, size_kb)
                if requested_at:
                    marker.write_text(requested_at)
            else:
                log.warning("Edge backup upload fejlede; Headend request bevares til retry")
        except Exception as exc:
            log.warning("Edge backup request fejlede: %s", exc, exc_info=True)

    def _create_edge_backup_archive(self, requested_at: str = "") -> tuple[Path, str, int]:
        """Create a small restore-oriented Edge backup archive without image payloads."""
        import hashlib as _hashlib
        import json as _json
        import os as _os
        import platform as _platform
        import shutil as _shutil
        import subprocess as _sp
        import tarfile as _tarfile
        import tempfile as _tempfile

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        device_id = self._device_id
        staging = Path(_tempfile.mkdtemp(prefix="tlp-edge-backup-"))
        archive = Path("/tmp") / f"timelapse-edge-backup-{device_id}-{timestamp}.tar.gz"
        try:
            (staging / "configs").mkdir(parents=True, exist_ok=True)
            (staging / "database").mkdir(parents=True, exist_ok=True)
            (staging / "system").mkdir(parents=True, exist_ok=True)

            copied: list[str] = []
            for source in [
                self._cfg_mgr.base_dir / "bootstrap.yaml",
                self._cfg_mgr.base_dir / "local_network.yaml",
                self._cfg_mgr.base_dir / "config.yaml",
                self._cfg_mgr.base_dir / "sftp_cache.yaml",
                Path("/etc/timelapse/node-agent.conf"),
                Path("/etc/systemd/system/timelapse-edge.service"),
                Path("/opt/timelapse/edge/scripts/timelapse-edge.service"),
            ]:
                if source.exists() and source.is_file():
                    dest = staging / "configs" / str(source).lstrip("/").replace("/", "__")
                    _shutil.copy2(source, dest)
                    copied.append(str(source))

            db_path = Path(self._cfg.get("storage", {}).get("db_path", "/data/timelapse_edge.db"))
            if db_path.exists():
                _shutil.copy2(db_path, staging / "database" / db_path.name)
                copied.append(str(db_path))

            commands = {
                "uname": ["uname", "-a"],
                "df": ["df", "-h"],
                "systemctl": ["systemctl", "is-active", "timelapse-edge"],
                "python": ["python3", "--version"],
            }
            system_info = {
                "device_id": device_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "requested_at": requested_at,
                "platform": _platform.platform(),
                "sensitive_identity_files_included": False,
                "note": "api_token.txt and signing keys are intentionally excluded; restore should re-bootstrap identity.",
                "commands": {},
            }
            for name, cmd in commands.items():
                try:
                    result = _sp.run(cmd, capture_output=True, text=True, timeout=20)
                    system_info["commands"][name] = {
                        "returncode": result.returncode,
                        "output": ((result.stdout or "") + (result.stderr or ""))[-4000:],
                    }
                except Exception as exc:
                    system_info["commands"][name] = {"returncode": -1, "output": str(exc)}

            manifest = {
                "device_id": device_id,
                "created_at": system_info["created_at"],
                "requested_at": requested_at,
                "copied": copied,
                "excluded": [
                    str(self._cfg_mgr.base_dir / "api_token.txt"),
                    str(self._cfg_mgr.base_dir / "keys"),
                    "/data/captures",
                ],
            }
            (staging / "system" / "SYSTEMINFO.json").write_text(_json.dumps(system_info, indent=2), encoding="utf-8")
            (staging / "MANIFEST.json").write_text(_json.dumps(manifest, indent=2), encoding="utf-8")

            with _tarfile.open(archive, "w:gz") as tar:
                tar.add(staging, arcname=f"timelapse-edge-backup-{device_id}-{timestamp}")

            hasher = _hashlib.sha256()
            with open(archive, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    hasher.update(chunk)
            return archive, hasher.hexdigest(), archive.stat().st_size // 1024
        finally:
            _shutil.rmtree(staging, ignore_errors=True)

    def _apply_config_changes(self, data: dict) -> None:
        """Anvend config-ændringer live uden genstart."""
        # SSH tunnel
        try:
            if hasattr(self, "_tunnel") and self._tunnel:
                tunnel_cfg = data.get("ssh_tunnel", {})
                self._tunnel.apply_config(tunnel_cfg)
                log.info("SSH tunnel config anvendt live")
        except Exception as exc:
            log.warning("SSH tunnel live apply fejl: %s", exc)

        # Lab mode
        try:
            debug_cfg = data.get("debug_mode", {})
            lab_now = debug_cfg.get("enabled", False)
            if lab_now:
                log.info("Lab mode aktiveret via config-ændring")
            else:
                log.info("Lab mode deaktiveret via config-ændring")
        except Exception as exc:
            log.warning("Lab mode live apply fejl: %s", exc)

        # Capture interval (træder i kraft ved næste søvncyklus)
        try:
            interval = self._cfg.get("schedule", {}).get("interval_minutes")
            if interval:
                log.info("Capture interval opdateret til %s min", interval)
        except Exception:
            pass

    BT_TOTP_CONFIG_PATH = Path("/etc/timelapse/bt-config.yaml")
    AUTHORIZED_TECHNICIANS_PATH = Path("/etc/timelapse/authorized_technicians.json")

    def _apply_technician_keys(self, keys: list[dict]) -> None:
        """Write the RBAC-replicated technician SSH public keys to a local
        cache, atomically. Read by edge/scripts/technician_authorized_keys.py
        via sshd's AuthorizedKeysCommand — no live headend round-trip needed
        at login time, so this keeps working while the device is offline,
        using whatever was last synced. First slice of the break-glass/RBAC
        redesign (2026-08-19, per Peter) — see Dokumentation/HANDOVER_LOG.md.
        Only public keys are handled here; nothing secret ever passes through
        this path.
        """
        path = self.AUTHORIZED_TECHNICIANS_PATH
        try:
            current_raw = path.read_text() if path.exists() else "[]"
            current = json.loads(current_raw)
        except Exception:
            current = None
        if current == keys:
            return  # allerede synkroniseret

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.tmp")
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(keys, fh)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
        os.chmod(path, 0o644)
        log.info("Technician SSH-nøgler synkroniseret fra headend (%d aktive)", len(keys))

    def _sync_bt_totp_config(self, bt_totp: dict) -> None:
        """Auto-synkronisér BT-TOTP secret fra headend til lokal totp-service.

        Erstatter kravet om at en tekniker manuelt klikker "Synkroniser TOTP
        fra CMDB" i /mgmt/*, hvilket kræver at allerede være logget ind lokalt
        — en høne-og-æg-deadlock for en enhed uden fabrikssecret
        (SEC-016-BOOTSTRAP-GAP). Enheden er allerede trust-forankret via
        device_id + API-token for selve config-hentningen (_verify_device_token
        på headend), så dette introducerer ingen ny tillidsgrænse — kun det
        allerede-autoriserede config-svar bliver nu også anvendt lokalt uden
        at kræve et separat manuelt klik.

        Delegates to utils.bt_totp_sync.sync_bt_totp_config(), which
        bootstrap_cli.py --totp-sync also calls, so there is one
        implementation of the actual file-write logic.
        """
        from utils.bt_totp_sync import sync_bt_totp_config
        sync_bt_totp_config(bt_totp, self.BT_TOTP_CONFIG_PATH)

    def _build_camera_commands(self) -> list[str]:
        """Byg kamera kommandoliste fra hierarkisk config.

        Starter med initial_commands fra device_config (bagud-kompatibilitet),
        derefter overskrives parametre fra camera.* overrides (kamera-laget).

        Mapping fra config nøgle til gphoto2 parameter navn:
          camera.iso           → imgsettings/iso
          camera.shutter_speed → capturesettings/shutterspeed
          camera.aperture      → capturesettings/aperture
          camera.whitebalance  → imgsettings/whitebalance
        """
        # Start med baseline initial_commands fra device_config
        commands: list[str] = list(
            self._cfg.get("camera", {}).get("initial_commands", [])
        )
        if hasattr(self._driver, "normalize_initial_commands"):
            commands = self._driver.normalize_initial_commands(commands)

        # Mapping: config nøgle → gphoto2 parameter navn
        PARAM_MAP = {
            "iso":          "iso",
            "shutter_speed": "shutterspeed",
            "aperture":     "aperture",
            "whitebalance": "whitebalance",
            "picturestyle": "picturestyle",
            "colorspace":   "colorspace",
            "imageformat":  "imageformat",
            "meteringmode": "meteringmode",
            "exposurecompensation": "exposurecompensation",
        }

        cam_cfg = self._cfg.get("camera", {})
        for cfg_key, gphoto_key in PARAM_MAP.items():
            value = self._effective_exposure_compensation() if cfg_key == "exposurecompensation" else cam_cfg.get(cfg_key)
            if value is None:
                continue
            if hasattr(self._driver, "build_config_command"):
                new_cmd = self._driver.build_config_command(cfg_key, str(value))
                if not new_cmd:
                    log.info("Config override skipped by camera profile: %s=%s", cfg_key, value)
                    continue
                prefix = new_cmd.split("=", 1)[0] + "="
            else:
                prefix = f"{gphoto_key}="
                new_cmd = f"{gphoto_key}={value}"
            # Erstat eksisterende kommando eller tilføj ny
            replaced = False
            for i, cmd in enumerate(commands):
                if cmd.startswith(prefix):
                    if commands[i] != new_cmd:
                        log.info("Config override: %s → %s (var: %s)", gphoto_key, value, cmd)
                        commands[i] = new_cmd
                    replaced = True
                    break
            if not replaced:
                commands.append(new_cmd)
                log.info("Config override: %s=%s (ny)", gphoto_key, value)

        return commands

    def _quality_report(self, filepath: Path, expected_sha256: str | None = None) -> dict:
        if hasattr(self._quality, "qa_report"):
            return self._quality.qa_report(filepath, expected_sha256)
        return self._quality.check(filepath, expected_sha256).as_dict()

    def _write_qa_sidecar(self, filepath: Path, quality_report: dict) -> None:
        try:
            qa_path = filepath.with_suffix(filepath.suffix + ".qa.json")
            payload = {
                "schema": "timelapse.edge_qa.v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "device_id": self._device_id,
                "image_file": filepath.name,
                "quality": quality_report,
            }
            qa_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.debug("Could not write QA sidecar for %s: %s", filepath.name, exc)

    def _effective_exposure_compensation(self) -> str | None:
        quality_cfg = self._cfg.get("quality", {})
        adaptive = quality_cfg.get("adaptive_exposure", {}) or {}
        cam_cfg = self._cfg.get("camera", {})
        base = cam_cfg.get("exposurecompensation")
        if not adaptive.get("enabled", False):
            return base
        base_ev = self._parse_ev(base, default=0.0)
        min_ev = float(adaptive.get("min_ev", -2.0))
        max_ev = float(adaptive.get("max_ev", 2.0))
        effective = max(min_ev, min(max_ev, base_ev + self._adaptive_exposure_ev))
        step = float(adaptive.get("step_ev", 0.3))
        return self._format_ev(effective, step)

    def _maybe_update_adaptive_exposure(self, quality_report: dict) -> None:
        adaptive = (self._cfg.get("quality", {}) or {}).get("adaptive_exposure", {}) or {}
        if not adaptive.get("enabled", False):
            return
        step = float(adaptive.get("step_ev", 0.3))
        min_ev = float(adaptive.get("min_ev", -2.0))
        max_ev = float(adaptive.get("max_ev", 2.0))
        optimizer = (quality_report.get("autonomous_optimizer") or {}).get("control_plan") or {}
        if optimizer:
            if optimizer.get("autonomous_safe_to_apply", False):
                try:
                    planned_delta = float(optimizer.get("next_capture_ev_delta", 0.0) or 0.0)
                except Exception:
                    planned_delta = 0.0
                if abs(planned_delta) >= 0.01:
                    self._adaptive_exposure_ev = max(
                        min_ev,
                        min(max_ev, self._adaptive_exposure_ev + planned_delta),
                    )
                    log.info(
                        "Adaptive exposure EV now %.2f from autonomous optimizer delta=%.2f",
                        self._adaptive_exposure_ev,
                        planned_delta,
                    )
            else:
                # Do not bypass a fail-closed optimizer decision with the legacy
                # single-frame rule. Decay gently toward the configured baseline.
                self._adaptive_exposure_ev *= 0.75
                log.info("Adaptive exposure held: optimizer marked plan unsafe")
            return
        cause = str(quality_report.get("probable_cause") or quality_report.get("flag") or "")
        brightness = quality_report.get("brightness_mean")
        delta = 0.0
        if cause in {"overexposed", "direct_sun_reflection"} or quality_report.get("flag") == "overexposed":
            delta = -step
        elif cause in {"underexposed", "underexposure_or_camera_blocked"} or quality_report.get("flag") == "underexposed":
            delta = step
        elif brightness is not None:
            target = float(adaptive.get("target_brightness", 118.0))
            tolerance = float(adaptive.get("brightness_tolerance", 32.0))
            if float(brightness) > target + tolerance:
                delta = -step
            elif float(brightness) < target - tolerance:
                delta = step
        if delta == 0.0:
            self._adaptive_exposure_ev *= 0.5
        else:
            self._adaptive_exposure_ev = max(min_ev, min(max_ev, self._adaptive_exposure_ev + delta))
        log.info("Adaptive exposure EV now %.2f after QA cause=%s brightness=%s", self._adaptive_exposure_ev, cause, brightness)

    @staticmethod
    def _parse_ev(value, default: float = 0.0) -> float:
        if value is None or value == "":
            return default
        raw = str(value).strip().replace("EV", "").replace("ev", "")
        raw = raw.replace(",", ".")
        try:
            return float(raw)
        except Exception:
            return default

    @staticmethod
    def _format_ev(value: float, step: float = 0.3) -> str:
        if step > 0:
            value = round(value / step) * step
        if abs(value) < 0.05:
            value = 0.0
        text = f"{value:+.1f}"
        return "0" if text in {"+0.0", "-0.0"} else text

    def _check_update(self) -> None:
        """Legacy LAB-only git update path.

        Production updates must be distributed by Headend as signed artifacts.
        """
        import subprocess, os
        update_requested = self._cfg.get("update_requested", False)
        if not update_requested:
            return
        legacy_enabled = (
            self._cfg.get("legacy_git_update_enabled") is True
            or os.getenv("TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE") == "1"
        )
        if not legacy_enabled:
            log.warning(
                "Legacy git update_requested ignoreret; Headend artifact update er påkrævet"
            )
            try:
                self._api._post(f"/admin/devices/{self._device_id}/clear-update", {})
            except Exception:
                pass
            return
        debug_cfg = self._cfg.get("debug_mode", {})
        if debug_cfg.get("enabled"):
            log.info("Opdatering anmodet men LAB mode aktiv — springer over")
            return
        version = self._cfg.get("update_version", "unknown")
        log.info("Opdatering anmodet — version %s", version)
        repo = "/opt/timelapse"
        try:
            git = "/usr/bin/git"
            import os
            env = os.environ.copy()
            env["HOME"] = "/home/orangepi"
            env["GIT_CONFIG_COUNT"] = "1"
            env["GIT_CONFIG_KEY_0"] = "safe.directory"
            env["GIT_CONFIG_VALUE_0"] = "*"
            # Fetch
            r = subprocess.run([git, "-C", repo, "fetch", "origin", "main", "--quiet"],
                               capture_output=True, text=True, env=env)
            if r.returncode != 0:
                log.warning("Opdatering fetch fejlede: %s", r.stderr.strip())
                return
            # Check versions
            current = subprocess.check_output([git, "-C", repo, "rev-parse", "HEAD"], env=env).decode().strip()
            remote  = subprocess.check_output([git, "-C", repo, "rev-parse", "origin/main"], env=env).decode().strip()
            if current == remote:
                log.info("Edge allerede opdateret — nulstiller update_requested flag")
                try:
                    self._api._post(f"/admin/devices/{self._device_id}/clear-update", {})
                except Exception:
                    pass
                return
            log.info("Opdaterer edge: %s → %s", current[:7], remote[:7])
            # Pull
            subprocess.run([git, "-C", repo, "pull", "origin", "main", "--quiet"], env=env)
            subprocess.run(["find", f"{repo}/edge", "-name", "__pycache__",
                           "-exec", "rm", "-rf", "{}", "+"])
            log.info("Opdatering OK — genstarter timelapse-edge")
            subprocess.run(["systemctl", "restart", "timelapse-edge"])
        except Exception as exc:
            log.warning("Opdatering fejl: %s", exc)



    @staticmethod
    def _pending_app_update_artifact(pending: dict) -> dict:
        return {
            "artifact_id": str(pending.get("artifact_id") or ""),
            "source_commit": str(pending.get("source_commit") or ""),
            "version": str(pending.get("version") or ""),
            "manifest": {"outputs": [{"path": raw} for raw in pending.get("outputs", [])]},
        }

    def _reconcile_pending_app_update(self) -> bool:
        """Reconcile durable post-restart evidence before accepting new work.

        Returns True whenever a pending lifecycle record exists, so update
        policy processing stays fail-closed until that exact release has either
        been confirmed healthy or rolled back.
        """
        repo = Path("/opt/timelapse")
        pending_path = pending_app_update_path(repo)
        try:
            pending = load_pending_app_update(pending_path)
        except Exception as exc:
            log.error("Pending app-update evidence er ugyldig; update-flow blokeret: %s", exc)
            return True
        if not pending:
            return False

        state = str(pending.get("state") or "")
        update_id = int(pending.get("update_id", -1))
        if update_id < 0:
            log.error("Pending app-update mangler update_id; update-flow blokeret")
            return True
        if state == "awaiting_restart_health":
            log.info("App update %d afventer komplet post-restart health gate", update_id)
            return True
        if state == "health_confirmed":
            if self._report_update(update_id, "deployed", "post_restart_health_confirmed"):
                cleanup_pending_app_update(pending_path)
                log.info("App update %d VERIFIED efter komplet startup; recovery evidence ryddet", update_id)
            return True
        if state == "rolled_back_by_guard":
            reason = str(pending.get("rollback_reason") or "post_restart_health_rollback")
            if self._report_update(update_id, "rolled_back", reason):
                cleanup_pending_app_update(pending_path)
                log.warning("App update %d rollback-evidence rapporteret og recovery ryddet", update_id)
            return True

        log.error("Ukendt pending app-update state=%s; update-flow blokeret", state)
        return True

    def _finalize_pending_app_update_health(self) -> None:
        """Confirm a candidate release only after the full startup path succeeded."""
        repo = Path("/opt/timelapse")
        pending_path = pending_app_update_path(repo)
        try:
            pending = load_pending_app_update(pending_path)
        except Exception as exc:
            log.error("Post-restart health kan ikke verificeres: %s", exc)
            return
        if not pending:
            return
        state = str(pending.get("state") or "")
        if state == "awaiting_restart_health":
            artifact = self._pending_app_update_artifact(pending)
            receipt = repo / "edge" / ".timelapse-release.json"
            if not release_receipt_matches_artifact(receipt, artifact):
                log.error(
                    "Post-restart health afvist for update %s: release receipt matcher ikke candidate identity",
                    pending.get("update_id"),
                )
                return
            try:
                mark_pending_app_update_health_confirmed(pending_path)
            except Exception as exc:
                log.error("Kunne ikke persistére post-restart health evidence: %s", exc)
                return
        self._reconcile_pending_app_update()

    def _check_and_apply_updates(self) -> None:
        """Tjek om der er godkendte opdateringer og eksekvér dem."""
        if not self._running or self._stop_event.is_set():
            return
        if self._reconcile_pending_app_update():
            return
        log.info("Update-check: starter...")
        self._last_update_check = datetime.now(timezone.utc)
        try:
            ok, policy = self._api._get(f"/updates/policy/{self._device_id}")
            if not ok or not policy:
                return
            self._apply_update_policy(policy)
        except Exception as e:
            log.warning("Update-check fejl: %s", e, exc_info=True)

    def _apply_update_policy(self, policy: dict) -> None:
        """Execute the first actionable item in an already-fetched update
        policy response. Split out of _check_and_apply_updates() so the
        consolidated sync poll (_run_sync) can apply a policy it received
        inline, without a second /updates/policy round-trip.
        """
        pending = policy.get("pending_updates", [])
        if not pending:
            return

        for update in pending:
            uid    = update["id"]
            utype  = update["update_type"]
            status = update["status"]

            if status == "rollback_requested":
                log.info("Rollback anmodet for opdatering %d (%s)", uid, utype)
                self._run_rollback(uid, utype, update.get("artifact"))
                return

            if status == "approved":
                ok, reason = verify_update_artifact(update, self._cfg.get("security", {}))
                if not ok:
                    log.error("Opdatering %d afvist af Edge trust policy: %s", uid, reason)
                    self._report_update(uid, "blocked", f"artifact_verification_failed: {reason}")
                    return
                artifact = update.get("artifact")
                receipt_path = Path("/opt/timelapse/edge/.timelapse-release.json")
                if artifact and release_receipt_matches_artifact(receipt_path, artifact):
                    log.info(
                        "Opdatering %d er allerede installeret ifølge durable release receipt; rapporterer deployed igen",
                        uid,
                    )
                    self._report_update(uid, "deployed", "release_receipt_already_matches_artifact")
                    return
                log.info("Udfører opdatering %d: %s", uid, utype)
                self._run_update(uid, utype, artifact)
                return  # Ét ad gangen

    def _run_update(self, update_id: int, update_type: str, artifact: dict | None = None) -> None:
        """Kør opdatering baseret på type og rapportér resultat."""
        import subprocess as _sp, os as _os

        if update_type in ("os_security", "os_updates"):
            if artifact:
                self._run_artifact_os_update(update_id, artifact)
                return
            log.warning("OS update %d blokeret: mangler Headend-signeret offline artifact", update_id)
            self._report_update(update_id, "blocked", "os_update_requires_headend_signed_offline_artifact")
            return
        else:
            if artifact:
                self._run_artifact_app_update(update_id, artifact)
                return
            legacy_allowed = (
                _os.getenv("TIMELAPSE_ENABLE_LEGACY_GIT_UPDATE") == "1"
                and _os.getenv("TIMELAPSE_ENV", "").strip().lower()
                in {"lab", "dev", "development", "rd"}
            )
            if not legacy_allowed:
                log.warning("App update %d afvist: Edge updates skal komme fra Headend artifact", update_id)
                self._report_update(update_id, "blocked", "headend_signed_artifact_required")
                return
            # LAB/dev/rd-only emergency path. Production Edge updates must use Headend artifacts.
            script = Path("/opt/timelapse/deploy/edge_update.sh")
            if not script.exists():
                log.warning("edge_update.sh ikke fundet")
                self._report_update(update_id, "blocked", "edge_update_script_missing")
                return
            env = {**_os.environ, "UPDATE_TYPE": update_type, "UPDATE_ID": str(update_id)}
            result = _sp.run(["bash", str(script)], capture_output=True, text=True, timeout=300, env=env)

        if result.returncode == 0:
            log.info("Opdatering %d gennemført OK", update_id)
            self._report_update(update_id, "deployed")
        else:
            log.warning("Opdatering %d fejlede (rc=%d)\n%s", update_id, result.returncode, result.stderr[-300:])
            self._report_update(update_id, "rolled_back", f"legacy_update_failed_rc_{result.returncode}: {result.stderr[-500:]}")

    def _report_update(self, update_id: int, status: str, reason: str | None = None) -> bool:
        payload = {
            "update_id": update_id,
            "status": status,
            "device_id": self._device_id,
        }
        if reason:
            payload["reason"] = reason
        try:
            ok, _ = self._api._post("/updates/report", payload)
            return bool(ok)
        except Exception as exc:
            log.warning("Update %d status=%s kunne ikke rapporteres: %s", update_id, status, exc)
            return False

    def _run_artifact_app_update(self, update_id: int, artifact: dict) -> None:
        """Installér app-opdatering fra Headend-signeret artifact uden GitHub adgang."""
        import hashlib as _hashlib
        import os as _os
        import shutil as _shutil
        import subprocess as _sp
        import tempfile as _tempfile

        artifact_id = artifact.get("artifact_id")
        manifest = artifact.get("manifest") if isinstance(artifact.get("manifest"), dict) else {}
        outputs = [
            item for item in manifest.get("outputs", [])
            if isinstance(item, dict) and str(item.get("path", "")).startswith("edge/")
        ]
        if not artifact_id or not outputs:
            log.warning("App update %d mangler edge artifact outputs", update_id)
            self._report_update(update_id, "blocked", "artifact_missing_edge_outputs")
            return

        repo = Path("/opt/timelapse")
        staging = Path(_tempfile.mkdtemp(prefix="tlp-artifact-", dir="/tmp"))
        backup = repo / "prev"
        receipt_path = repo / "edge" / ".timelapse-release.json"
        safe_artifact_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(artifact_id or "artifact"))[:80]
        recovery_root = Path("/data/timelapse_update_recovery")
        recovery_dir = recovery_root / f"app-{update_id}-{safe_artifact_id}"
        pending_path = pending_app_update_path(repo)
        unit_backup = recovery_dir / "systemd-backup"
        guard_started = False
        rollback_ready = False
        managed_units = (
            "timelapse-bt-pan.service",
            "timelapse-bt-agent.service",
            "timelapse-captive.service",
            "timelapse-totp.service",
        )
        managed_unit_files = (*managed_units, "timelapse-edge.service")
        management_runtime_paths = {
            "edge/scripts/timelapse-bt-pan.sh",
            "edge/scripts/bt-autoagent.py",
            "edge/scripts/totp-service.py",
            "edge/scripts/timelapse-captive.sh",
            "edge/scripts/gen-bt-cert.sh",
            *(f"edge/scripts/{unit}" for unit in managed_unit_files),
        }
        management_changed = any(
            str(item.get("path")) in management_runtime_paths for item in outputs
        )
        try:
            if pending_path.exists():
                raise RuntimeError("pending_app_update_recovery_exists")
            if recovery_dir.exists():
                _shutil.rmtree(recovery_dir)
            recovery_dir.mkdir(parents=True, mode=0o700)

            self._report_update(update_id, "backing_up")
            pre_archive, pre_sha, pre_size_kb = self._create_edge_backup_archive(f"pre-update-{update_id}")
            pre_ok, pre_result = self._api.upload_edge_backup(pre_archive, pre_sha)
            if not pre_ok:
                raise RuntimeError("pre_update_backup_upload_failed")
            log.info(
                "App update %d pre-update backup OK: %s (%d KB)",
                update_id,
                pre_archive.name,
                pre_size_kb,
            )
            self._report_update(update_id, "downloading")
            log.info("App update %d: henter %d edge-filer fra artifact %s", update_id, len(outputs), artifact_id)
            for item in outputs:
                rel = str(item["path"])
                if rel.startswith("/") or ".." in Path(rel).parts:
                    raise RuntimeError(f"unsafe artifact path: {rel}")
                ok, content = self._api.download_artifact_file(artifact_id, rel)
                if not ok or content is None:
                    raise RuntimeError(f"download failed: {rel}")
                actual = _hashlib.sha256(content).hexdigest()
                if actual != item.get("sha256"):
                    raise RuntimeError(f"sha256 mismatch: {rel}")
                dest = staging / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)

            self._report_update(update_id, "verifying")
            if backup.exists():
                _shutil.rmtree(backup)
            if receipt_path.is_file():
                backup_receipt = backup / "edge" / receipt_path.name
                backup_receipt.parent.mkdir(parents=True, exist_ok=True)
                _shutil.copy2(receipt_path, backup_receipt)
            for item in outputs:
                rel = Path(str(item["path"]))
                source = repo / rel
                if source.exists():
                    backup_dest = backup / rel
                    backup_dest.parent.mkdir(parents=True, exist_ok=True)
                    _shutil.copy2(source, backup_dest)
            rollback_ready = True

            self._report_update(update_id, "installing")
            for item in outputs:
                rel = Path(str(item["path"]))
                source = staging / rel
                dest = repo / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                _shutil.copy2(source, dest)
                if dest.suffix == ".sh":
                    dest.chmod(dest.stat().st_mode | 0o111)

            if management_changed:
                # These components run as independent root-owned services.
                # Copy their signed artifact files into the active systemd
                # locations, then restart and verify them before marking the
                # deployment successful.  Backups are kept outside ``prev``
                # so the application rollback loop never copies them into the
                # repository tree.
                unit_backup.mkdir(parents=True, exist_ok=True)
                # Complete the recovery snapshot and validate every candidate
                # unit before mutating the active systemd directory.
                for unit in managed_unit_files:
                    target = Path("/etc/systemd/system") / unit
                    if target.exists():
                        _shutil.copy2(target, unit_backup / unit)
                    source = repo / "edge" / "scripts" / unit
                    if not source.is_file():
                        raise RuntimeError(f"managed_systemd_unit_missing:{unit}")
                for unit in managed_unit_files:
                    source = repo / "edge" / "scripts" / unit
                    target = Path("/etc/systemd/system") / unit
                    _shutil.copy2(source, target)
                _sp.run(["systemctl", "daemon-reload"], check=True, capture_output=True, text=True)
                for service in managed_unit_files:
                    _sp.run(["systemctl", "enable", service], check=True, capture_output=True, text=True)

                # Bluetooth hardware or its vendor driver can be unavailable
                # on an otherwise healthy Edge.  That must be visible, but it
                # must not roll back a verified application release.  Captive
                # firewall activation is only meaningful after PAN made br-bt.
                _sp.run(
                    ["systemctl", "restart", "timelapse-bt-pan.service"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                bt_pan_active = _sp.run(
                    ["systemctl", "is-active", "--quiet", "timelapse-bt-pan.service"],
                    check=False,
                    capture_output=True,
                    text=True,
                ).returncode == 0
                if bt_pan_active:
                    _sp.run(
                        ["systemctl", "restart", "timelapse-bt-agent.service"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    service = "timelapse-captive.service"
                    _sp.run(["systemctl", "restart", service], check=True, capture_output=True, text=True)
                    active = _sp.run(
                        ["systemctl", "is-active", "--quiet", service],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if active.returncode != 0:
                        raise RuntimeError(f"managed_service_not_active:{service}")
                else:
                    log.warning(
                        "App update %d: Bluetooth PAN er ikke aktiv; captive firewall afventer PAN-recovery",
                        update_id,
                    )

                for service in ("timelapse-totp.service",):
                    _sp.run(["systemctl", "restart", service], check=True, capture_output=True, text=True)
                    active = _sp.run(
                        ["systemctl", "is-active", "--quiet", service],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if active.returncode != 0:
                        raise RuntimeError(f"managed_service_not_active:{service}")

            # Artifact copies do not move the local Git checkout. Receipt
            # persistence is therefore a hard deployment gate: CMDB must not
            # report deployed until the durable identity can be read back.
            release_receipt = {
                "schema": "timelapse.edge.release.v1",
                "artifact_id": str(artifact_id),
                "source_commit": str(artifact.get("source_commit") or manifest.get("source_commit") or ""),
                "version": str(artifact.get("version") or manifest.get("version") or ""),
                "installed_at": datetime.now(timezone.utc).isoformat(),
            }
            receipt_tmp = receipt_path.with_name(f".{receipt_path.name}.tmp-{_os.getpid()}")
            flags = _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC | getattr(_os, "O_NOFOLLOW", 0)
            fd = _os.open(receipt_tmp, flags, 0o644)
            try:
                with _os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(release_receipt, handle, sort_keys=True)
                    handle.flush()
                    _os.fsync(handle.fileno())
                _os.replace(receipt_tmp, receipt_path)
                receipt_path.chmod(0o644)
            finally:
                if receipt_tmp.exists():
                    receipt_tmp.unlink()
            persisted_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if persisted_receipt != release_receipt:
                raise RuntimeError("release_receipt_readback_mismatch")
            log.info("App update %d release receipt persisted: %s", update_id, receipt_path)

            guard_managed_units = managed_unit_files if management_changed else ()
            write_pending_app_update(
                pending_path,
                update_id=update_id,
                artifact=artifact,
                recovery_dir=recovery_dir,
                managed_unit_files=guard_managed_units,
                health_timeout_s=int(
                    self._cfg.get("updates", {}).get("post_restart_health_timeout_s", 180)
                ),
                repo=repo,
            )
            guard_runner = write_post_restart_guard(recovery_dir)
            python_runtime = Path("/opt/timelapse/venv/bin/python")
            if not python_runtime.is_file():
                raise RuntimeError("edge_python_runtime_missing_for_post_restart_guard")
            guard_unit = f"timelapse-app-update-guard-{update_id}"
            guard_result = _sp.run(
                [
                    "/usr/bin/systemd-run",
                    f"--unit={guard_unit}",
                    "--collect",
                    "--no-block",
                    "-p", "NoNewPrivileges=yes",
                    "-p", "PrivateTmp=yes",
                    str(python_runtime),
                    str(guard_runner),
                    str(pending_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            if guard_result.returncode != 0:
                raise RuntimeError(
                    f"post_restart_guard_start_failed:{guard_result.stderr[-400:]}"
                )
            guard_active = False
            for _ in range(10):
                active = _sp.run(
                    ["systemctl", "is-active", "--quiet", guard_unit],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if active.returncode == 0:
                    guard_active = True
                    break
                time.sleep(0.2)
            if not guard_active:
                raise RuntimeError("post_restart_guard_not_active")
            guard_started = True
            self._report_update(update_id, "installing", "awaiting_post_restart_health")
            log.info(
                "App update %d candidate installeret; separat guard aktiv — genstarter agent før deployed-status",
                update_id,
            )
            _sp.Popen(["systemctl", "restart", "timelapse-edge"])
        except Exception as exc:
            log.warning("App artifact update %d fejlede: %s", update_id, exc)
            if guard_started:
                # The independent guard now owns candidate verification and
                # rollback.  Do not race it with an in-process restore.
                self._report_update(
                    update_id,
                    "installing",
                    f"post_restart_guard_active_after_restart_error:{str(exc)[:500]}",
                )
            else:
                try:
                    if unit_backup.exists():
                        for unit in managed_unit_files:
                            previous = unit_backup / unit
                            target = Path("/etc/systemd/system") / unit
                            if previous.is_file():
                                _shutil.copy2(previous, target)
                            elif management_changed and target.exists():
                                _sp.run(["systemctl", "stop", unit], check=False, capture_output=True, text=True)
                                target.unlink()
                        _sp.run(["systemctl", "daemon-reload"], check=False, capture_output=True, text=True)
                        for service in managed_units:
                            if (unit_backup / service).is_file():
                                _sp.run(["systemctl", "try-restart", service], check=False, capture_output=True, text=True)
                except Exception as service_rollback_exc:
                    log.warning("Rollback af lokale management-services fejlede: %s", service_rollback_exc)
                try:
                    if rollback_ready and backup.exists():
                        restore_previous_app_release(repo, artifact)
                except Exception as rollback_exc:
                    log.warning("Rollback efter app artifact update fejlede: %s", rollback_exc)
                try:
                    if pending_path.exists():
                        cleanup_pending_app_update(pending_path)
                    elif recovery_dir.exists():
                        _shutil.rmtree(recovery_dir)
                except Exception as cleanup_exc:
                    log.warning("Cleanup af app-update recovery evidence fejlede: %s", cleanup_exc)
                self._report_update(update_id, "rolled_back", str(exc)[:700])
        finally:
            try:
                _shutil.rmtree(staging)
            except Exception:
                pass

    def _run_artifact_os_update(self, update_id: int, artifact: dict) -> None:
        """Installér OS-opdatering fra Headend-signeret offline artifact."""
        import hashlib as _hashlib
        import os as _os
        import shlex as _shlex
        import shutil as _shutil
        import subprocess as _sp

        artifact_id = artifact.get("artifact_id")
        manifest = artifact.get("manifest") if isinstance(artifact.get("manifest"), dict) else {}
        outputs = [item for item in manifest.get("outputs", []) if isinstance(item, dict)]
        commands = [cmd for cmd in manifest.get("commands", []) if isinstance(cmd, dict)]
        safe_artifact_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(artifact_id or "artifact"))[:80]
        staging_root = Path("/data/timelapse_update_staging")
        staging = staging_root / f"update-{update_id}-{safe_artifact_id}"
        try:
            if staging.exists():
                _shutil.rmtree(staging)
            staging.mkdir(parents=True, mode=0o700)
            if manifest.get("schema") != "timelapse.os_update_artifact.v1":
                raise RuntimeError("invalid_os_artifact_schema")
            if manifest.get("distribution_model") != "headend_signed_offline_os_bundle_edge_pull":
                raise RuntimeError("invalid_os_distribution_model")
            if not artifact_id or not outputs:
                raise RuntimeError("os_artifact_missing_outputs")

            self._report_update(update_id, "backing_up")
            pre_archive, pre_sha, pre_size_kb = self._create_edge_backup_archive(f"pre-os-update-{update_id}")
            pre_ok, _pre_result = self._api.upload_edge_backup(pre_archive, pre_sha)
            if not pre_ok:
                raise RuntimeError("pre_update_backup_upload_failed")
            log.info("OS update %d pre-update backup OK: %s (%d KB)", update_id, pre_archive.name, pre_size_kb)

            self._report_update(update_id, "downloading")
            for item in outputs:
                rel = str(item.get("path") or "")
                if not rel or rel.startswith("/") or ".." in Path(rel).parts:
                    raise RuntimeError(f"unsafe artifact path: {rel}")
                ok, content = self._api.download_artifact_file(artifact_id, rel)
                if not ok or content is None:
                    raise RuntimeError(f"download failed: {rel}")
                actual = _hashlib.sha256(content).hexdigest()
                if actual != item.get("sha256"):
                    raise RuntimeError(f"sha256 mismatch: {rel}")
                dest = staging / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)

            self._report_update(update_id, "verifying")
            forbidden_script_patterns = [
                r"\bapt(-get)?\s+update\b",
                r"\bapt(-get)?\s+(dist-upgrade|full-upgrade|upgrade)\b",
                r"^\s*(curl|wget|scp|rsync)\b",
                r"^\s*git\s+(clone|pull|fetch)\b",
                r"^\s*python3?\s+-m\s+pip\b",
                r"^\s*pip3?\s+install\b",
            ]
            for script_path in staging.rglob("*"):
                if not script_path.is_file() or script_path.suffix not in {".sh", ".bash", ".conf", ".txt", ".json"}:
                    continue
                content = script_path.read_text(errors="ignore")
                rel_script = str(script_path.relative_to(staging))
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    for pattern in forbidden_script_patterns:
                        if re.search(pattern, stripped):
                            raise RuntimeError(f"os bundle contains forbidden online command: {rel_script}")
                    if "apt-get" in line or " apt " in line:
                        if "--no-download" not in line:
                            raise RuntimeError(f"os bundle apt command without --no-download: {rel_script}")

            if not commands:
                raise RuntimeError("os_artifact_missing_install_commands")

            self._report_update(update_id, "installing")
            allowed_roots = {str(staging), "/usr/bin", "/bin", "/usr/sbin", "/sbin"}
            runner_lines = [
                "#!/bin/bash",
                "set -euo pipefail",
                "export DEBIAN_FRONTEND=noninteractive",
                f"cd {_shlex.quote(str(staging))}",
            ]
            for command in commands:
                argv = command.get("argv")
                if not isinstance(argv, list) or not argv:
                    raise RuntimeError("invalid_os_command")
                argv = [str(a).replace("{bundle}", str(staging)) for a in argv]
                executable = str(argv[0])
                if "/" in executable and not any(executable.startswith(root) for root in allowed_roots):
                    raise RuntimeError(f"os command outside allowed roots: {executable}")
                joined = " ".join(argv)
                if any(token in joined for token in (" apt-get update", " apt update", " apt-get upgrade", " apt upgrade", "dist-upgrade", "full-upgrade")):
                    raise RuntimeError("os artifact command may not run online apt update/upgrade")
                if "apt-get" in joined or " apt " in joined:
                    if "--no-download" not in argv and "--no-download" not in joined:
                        raise RuntimeError("apt command must use --no-download")
                if executable in {"apt-get", "apt"}:
                    argv = ["/usr/bin/apt-get", *[str(a) for a in argv[1:]]]
                    if "upgrade" in argv or "dist-upgrade" in argv or "--no-download" not in argv:
                        raise RuntimeError("apt command must be explicit install with --no-download")
                runner_lines.append(" ".join(_shlex.quote(str(a)) for a in argv))

            runner = staging / "run-os-update.sh"
            runner.write_text("\n".join(runner_lines) + "\n")
            runner.chmod(0o700)
            systemd_run = [
                "/usr/bin/systemd-run",
                "--wait",
                "--pipe",
                "--collect",
                f"--unit=timelapse-os-update-{update_id}",
                "-p",
                "ProtectSystem=false",
                "-p",
                "NoNewPrivileges=false",
                "-p",
                "PrivateTmp=false",
                "-p",
                "ReadWritePaths=/",
                "/bin/bash",
                str(runner),
            ]
            result = _sp.run(
                    systemd_run,
                    capture_output=True,
                    text=True,
                    timeout=max(1800, sum(int(command.get("timeout_s") or 1800) for command in commands)),
                    env={**_os.environ, "DEBIAN_FRONTEND": "noninteractive"},
                )
            combined_output = (result.stdout or "") + (result.stderr or "")
            log.info("OS update %d systemd-run rc=%d\n%s", update_id, result.returncode, combined_output[-2000:])
            if result.returncode != 0:
                raise RuntimeError(f"os artifact install failed rc={result.returncode}\n{combined_output[-1600:]}")

            self._report_update(update_id, "deployed")
            log.info("OS update %d installeret fra offline artifact", update_id)
        except Exception as exc:
            log.warning("OS artifact update %d fejlede: %s", update_id, exc)
            self._report_update(update_id, "blocked", str(exc)[:700])
        finally:
            try:
                _shutil.rmtree(staging)
            except Exception:
                pass

    def _run_rollback(self, update_id: int, update_type: str, artifact: dict | None = None) -> None:
        """Tving rollback af en app-release via den lokale, verificerbare prev-kopi."""
        import subprocess as _sp

        if update_type in ("os_security", "os_updates"):
            log.warning("OS rollback %d afvist: offline OS-flowet lover ikke rollback", update_id)
            self._report_update(update_id, "blocked", "os_forced_rollback_not_supported")
            return

        try:
            result = restore_previous_app_release(Path("/opt/timelapse"), artifact)
        except FileNotFoundError:
            log.warning("Ingen forrige app-version til rollback")
            self._report_update(update_id, "blocked", "rollback_source_missing")
            return
        except Exception as exc:
            log.warning("Tvungen rollback %d fejlede: %s", update_id, exc)
            self._report_update(update_id, "blocked", f"forced_rollback_failed: {str(exc)[:500]}")
            return

        log.info(
            "Rollback til forrige app-version gennemført: restored=%s removed_new=%s",
            result.get("restored_files"),
            result.get("removed_new_files"),
        )
        self._report_update(update_id, "rolled_back")
        _sp.Popen(["systemctl", "restart", "timelapse-edge"])

    def _send_heartbeat(self, *, check_updates: bool = True) -> None:
        """Collect diagnostics and send heartbeat to headend."""
        try:
            diag_data     = self._diag.collect()
            capture_stats = self._db.capture_stats(self._device_id)
            # Headend's app-update auto-detection (_process_update_report) reads
            # diag["updates"]["app_version"] on every heartbeat — without this the
            # collector never carried it, so a newer Headend release was never
            # auto-detected outside of a manual DB insert. See
            # Dokumentation/HANDOVER_LOG.md 2026-08-19.
            from utils.inventory import current_app_version
            diag_data["updates"] = {"app_version": current_app_version()}
            self._db.insert_diagnostics(self._device_id, diag_data)

            # Include last camera diagnostics from capture cycle
            if hasattr(self, "_last_cam_diag") and self._last_cam_diag:
                diag_data["camera"] = self._last_cam_diag

            ok, hb_resp = self._api.send_heartbeat(diag_data, capture_stats)
            if ok:
                log.info("Heartbeat sent OK")
                self._connectivity.report_success()
                # NTP: synkroniser systemtid fra headend
                self._sync_time_from_headend(hb_resp)
                # Tjek om config er ændret siden sidst
                hb_version = (hb_resp or {}).get("config_version", "") if isinstance(hb_resp, dict) else ""
                if hb_version and hb_version != self._cfg.get("config_version", ""):
                    log.info("Config version ændret via heartbeat — henter ny config")
                    self._pull_config()
                # Periodisk inventory-rapportering (dagligt)
                self._report_inventory()
            else:
                log.warning("Heartbeat failed — headend unreachable")
                self._connectivity.report_failure()
        except Exception as exc:
            log.warning("Heartbeat error: %s", exc)
            self._connectivity.report_failure()
        finally:
            self._last_heartbeat = datetime.now(timezone.utc)
            if check_updates and self._running and not self._stop_event.is_set():
                self._check_and_apply_updates()

    def _sync_time_from_headend(self, hb_resp: dict | None) -> None:
        """Synkroniser systemtid fra headend server_time. Kræver root."""
        if not isinstance(hb_resp, dict):
            return
        server_time_str = hb_resp.get("server_time")
        if not server_time_str:
            return
        try:
            from datetime import datetime as _dt
            import subprocess as _sp
            server_dt = _dt.fromisoformat(server_time_str.replace("Z", "+00:00"))
            local_dt  = _dt.now(timezone.utc)
            drift_s   = abs((server_dt - local_dt).total_seconds())
            if drift_s < 5:
                return  # inden for 5 sek — ingen handling
            # Formater til date-kommando: "YYYY-MM-DD HH:MM:SS"
            date_str = server_dt.strftime("%Y-%m-%d %H:%M:%S")
            result = _sp.run(
                ["date", "-s", date_str],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                log.info("NTP sync fra headend: drift=%.1fs → sat til %s", drift_s, date_str)
                # Skriv til hardware clock hvis muligt
                _sp.run(["hwclock", "--systohc"], capture_output=True, timeout=5)
            else:
                log.warning("NTP sync fejlede (mangler root?): %s", result.stderr.strip())
        except Exception as exc:
            log.warning("NTP sync error: %s", exc)

    def _report_inventory(self, *, force: bool = False) -> None:
        """Rapportér CMDB hardware-inventar til headend. Dagligt eller ved force=True."""
        now = datetime.now(timezone.utc)
        interval_h = float(self._cfg.get("diagnostics", {}).get("inventory_report_interval_hours", 24))
        if not force and (now - self._last_inventory).total_seconds() < interval_h * 3600:
            return
        try:
            from utils.inventory import report_inventory
            # Tilføj HAL-capabilities til inventory
            hal_caps = _HAL_ADAPTER.capabilities() if _HAL_ADAPTER else {}
            report_inventory(self._cfg, self._api, extra={"hal": hal_caps})
            self._last_inventory = now
            log.info("Inventory rapporteret til headend CMDB (hal_id=%s)",
                     hal_caps.get("hal_id", "unknown"))
        except Exception as exc:
            log.warning("Inventar-rapportering fejlede: %s", exc)

    def _collect_inventory_if_due(self, *, force: bool = False) -> dict | None:
        """Build the CMDB inventory payload when due, for inclusion in the
        consolidated sync poll instead of _report_inventory()'s own separate
        POST. Same interval/force semantics and shared _last_inventory gate —
        whichever path fires first (this or an ad-hoc _report_inventory() call
        from _send_heartbeat) consumes the due window, so inventory is never
        reported twice.
        """
        now = datetime.now(timezone.utc)
        interval_h = float(self._cfg.get("diagnostics", {}).get("inventory_report_interval_hours", 24))
        if not force and (now - self._last_inventory).total_seconds() < interval_h * 3600:
            return None
        try:
            from utils.inventory import collect_inventory
            hal_caps = _HAL_ADAPTER.capabilities() if _HAL_ADAPTER else {}
            payload = collect_inventory(self._cfg)
            payload["hal"] = hal_caps
            if not payload.get("hardware_model"):
                payload["hardware_model"] = hal_caps.get("hal_id")
            return payload
        except Exception as exc:
            log.warning("Inventar-indsamling fejlede: %s", exc)
            return None

    def _run_sync(self) -> None:
        """Single consolidated poll: diagnostics/app_version/SIEM events
        (and, when due, CMDB inventory) go out; config/pending-updates come
        back. One HTTP request instead of what used to be three
        independently-timed loops (config-pull, heartbeat, SIEM-forward)
        plus a redundant nested update-check timer. Composes the same apply
        logic _pull_config()/_check_and_apply_updates() already used, just
        fed from an already-fetched response instead of a fresh round-trip.
        See headend/edge_sync.py and Dokumentation/HANDOVER_LOG.md 2026-08-19.
        """
        try:
            diag_data = self._diag.collect()
            from utils.inventory import current_app_version
            diag_data["updates"] = {"app_version": current_app_version()}
            capture_stats = self._db.capture_stats(self._device_id)
            self._db.insert_diagnostics(self._device_id, diag_data)
            if hasattr(self, "_last_cam_diag") and self._last_cam_diag:
                diag_data["camera"] = self._last_cam_diag

            siem_events = self._collect_siem_events_for_sync()
            inventory_payload = self._collect_inventory_if_due()

            ok, resp = self._api.sync(diag_data, capture_stats, siem_events, inventory_payload)
            if ok and resp:
                log.info("Sync poll sent OK")
                self._connectivity.report_success()
                self._sync_time_from_headend(resp)
                if inventory_payload is not None:
                    self._last_inventory = datetime.now(timezone.utc)
                    log.info("Inventory rapporteret til headend CMDB (via sync poll)")
                if siem_events:
                    self._persist_siem_cursor_after_sync()
                config = resp.get("config")
                if config:
                    self._apply_fetched_config(config)
                try:
                    self._apply_technician_keys(resp.get("technician_keys", []))
                except Exception as tech_exc:
                    # Must not block update-policy processing below — an update
                    # is often exactly what fixes a broken technician-key write
                    # (e.g. a stale sandbox ReadWritePaths). Found 2026-08-24:
                    # a device stuck on the pre-fix agent could never receive
                    # the fixing update, because this exception used to abort
                    # the rest of _run_sync() before reaching _apply_update_policy.
                    log.warning("Technician-nøgle synkronisering fejlede: %s", tech_exc)
                if not self._reconcile_pending_app_update():
                    self._apply_update_policy(resp)
            else:
                log.warning("Sync poll failed — headend unreachable")
                self._connectivity.report_failure()
        except Exception as exc:
            log.warning("Sync poll error: %s", exc)
            self._connectivity.report_failure()
        finally:
            self._last_heartbeat = datetime.now(timezone.utc)

    def _sync_captures(self) -> None:
        """Sync unsynced capture metadata to headend API."""
        try:
            unsynced = self._db.get_unsynced_captures(limit=100)
            if not unsynced:
                return
            log.debug("Syncing %d captures to headend…", len(unsynced))
            for row in unsynced:
                ok, _ = self._api.sync_capture(row)
                if ok:
                    self._db.mark_synced(row["id"])
        except Exception as exc:
            log.warning("Capture sync error: %s", exc)

    def _upload_capture_transports(self, capture_id: int, filepath: Path, camera_id: str) -> dict[str, bool]:
        """Upload a capture through primary API and optional SFTP destinations."""
        results: dict[str, bool] = {}
        row = self._db.get_capture(capture_id) if capture_id else None
        if row:
            allowed, wait_s, remaining_s = self._upload_slot_state()
            if not allowed:
                log.info(
                    "API upload deferred by Headend slot: capture_id=%s filename=%s next_slot_in_s=%s",
                    capture_id,
                    filepath.name,
                    wait_s,
                )
                results["primary"] = False
                results["api_primary"] = False
                return results
            log.info("API upload slot open: remaining_s=%s", remaining_s)
            ok, _ = self._api.upload_capture_files(row, filepath)
            results["primary"] = ok
            results["api_primary"] = ok
            if ok:
                self._db.mark_uploaded(capture_id, "primary")
        else:
            results["primary"] = False
            results["api_primary"] = False
        sftp_results = self._uploader.upload_capture(capture_id, filepath, camera_id)
        results.update(sftp_results)
        return results

    def _retry_pending_uploads_if_slot(self) -> None:
        allowed, wait_s, remaining_s = self._upload_slot_state()
        if not allowed:
            return
        retried = self._retry_pending_api_uploads()
        if retried:
            log.info("API upload slot processed pending files: count=%d remaining_s=%s", retried, remaining_s)

    def _retry_pending_api_uploads(self) -> int:
        """Retry primary API uploads from the local store-and-forward queue."""
        count = 0
        try:
            max_pending = int(
                self._cfg.get("upload", {})
                .get("api", {})
                .get("timeslot", {})
                .get("max_pending_per_window", 3)
            )
            for row in self._db.get_pending_uploads("primary", limit=max(1, max_pending)):
                filepath = Path(row["filepath"])
                if not filepath.exists():
                    continue
                ok, _ = self._api.upload_capture_files(row, filepath)
                if ok:
                    self._db.mark_uploaded(row["id"], "primary")
                    count += 1
        except Exception as exc:
            log.warning("API upload retry error: %s", exc)
        return count

    def _upload_slot_state(self, now: datetime | None = None) -> tuple[bool, int, int]:
        slot = (
            self._cfg.get("upload", {})
            .get("api", {})
            .get("timeslot", {})
        )
        if not slot or not slot.get("enabled", False):
            return True, 0, 999999
        if not slot.get("enforced", False):
            return True, 0, 999999
        cycle_s = max(1, int(slot.get("cycle_seconds", 600)))
        window_s = max(1, int(slot.get("window_seconds", 90)))
        offset_s = int(slot.get("start_offset_seconds", 0)) % cycle_s
        now = now or datetime.now(timezone.utc)
        phase = int(now.timestamp()) % cycle_s
        elapsed = (phase - offset_s) % cycle_s
        if elapsed < window_s:
            return True, 0, window_s - elapsed
        wait_s = (cycle_s - elapsed) % cycle_s
        if wait_s == 0:
            wait_s = cycle_s
        return False, wait_s, 0

    # ── Lab / debug mode ────────────────────────────────────────────────────

    def _lab_tick(self, debug_cfg: dict) -> None:
        """
        Lab mode tick — relay stays ON, polls for commands from headend.
        Supports: preview capture, full capture, set-param, relay toggle.
        Poll interval: debug_cfg.config_poll_s (default 1 second).
        """
        poll_s = int(debug_cfg.get("config_poll_s", 1))

        # LAB mode has its own loop and does not pass through _tick(). Keep the
        # signed Headend update policy active while a camera session is open.
        self._check_and_apply_updates_if_due()

        ok, cfg_data = self._api.fetch_config()
        if ok and cfg_data:
            old_version = self._cfg.get("config_version", "")
            new_version = cfg_data.get("config_version", "")
            if new_version and new_version != old_version:
                old_power_mode = self._camera_power_mode()
                self._cfg_mgr.save_config(cfg_data)
                self._cfg = self._cfg_mgr.load()
                self._uploader.update_config(cfg_data)
                self._apply_config_changes(cfg_data)
                self._last_config_pull = datetime.now(timezone.utc)
                new_power_mode = self._camera_power_mode()
                log.info(
                    "LAB MODE — config version changed %s→%s power_mode=%s→%s",
                    old_version[:8], new_version[:8], old_power_mode, new_power_mode,
                )
                if old_power_mode != new_power_mode:
                    try:
                        self._driver.disconnect()
                    except Exception:
                        pass
                    self._lab_relay_on = False

        # Ensure camera is ready
        if not getattr(self, "_lab_relay_on", False):
            log.info("LAB MODE — preparing camera (power_mode=%s)", self._camera_power_mode())
            lab_session = None
            if getattr(self, "_service_platform", None):
                lab_session = self._service_platform.shared_or_lab_session("lab")
                self._lab_service_session = lab_session
                self._service_platform.call("camera.power.acquire", session=lab_session)

            # Initialize relay flag for this initialization cycle
            if not getattr(self, "_service_platform", None):
                self._lab_relay_on = False

            # Track consecutive camera connection failures for auto-powercycle
            conn_failures = getattr(self, "_lab_cam_connect_failures", 0)
            max_retries = 2  # Retry once before powercycle, then powercycle + retry

            for attempt in range(max_retries + 1):
                if attempt > 0:
                    if attempt == 1:
                        log.info("LAB MODE — Retry camera connection (attempt %d/%d)", attempt + 1, max_retries + 1)
                        time.sleep(2)  # Brief pause before retry
                    elif attempt == 2:
                        # Second failure - powercycle camera
                        log.warning("LAB MODE — Camera connection failed twice, power cycling...")
                        self._camera_power_off("camera connect failure", force=True)
                        time.sleep(5)  # Wait for full discharge
                        log.info("LAB MODE — Powering camera back on after cycle...")
                        self._camera_power_on("lab mode retry")
                        warmup_s = self._camera_warmup_seconds()
                        if warmup_s:
                            log.info("LAB MODE — Waiting %ds for camera warm-up after power cycle...", warmup_s)
                            time.sleep(warmup_s)

                try:
                    # Power on if not already on
                    if not self._lab_relay_on or attempt == 0:
                        self._camera_power_on("lab mode")
                        self._lab_relay_on = True
                        warmup_s = self._camera_warmup_seconds()
                        if warmup_s:
                            time.sleep(warmup_s)

                    self._driver.connect()
                    commands = self._build_camera_commands()
                    if commands:
                        self._driver.apply_initial_commands(commands)
                    log.info("LAB MODE — camera connected and ready")
                    # Signal til headend at kamera er klar
                    try:
                        _, resp = self._api._post("/lab/" + self._device_id + "/camera-ready", {"ready": True})
                        self._check_config_version(resp)
                    except Exception:
                        pass

                    # Success! Reset failure counter
                    self._lab_cam_connect_failures = 0

                    # Frame push should ONLY start when user explicitly enables it via MJPEG Live button
                    # Do NOT auto-start here - self._live_frame_enabled should only be set by user action
                    break  # Success - exit retry loop

                except Exception as exc:
                    conn_failures += 1
                    self._lab_cam_connect_failures = conn_failures
                    log.warning("LAB MODE — camera connect attempt %d failed: %s", attempt + 1, exc)

                    if attempt >= max_retries:
                        # All retries exhausted - critical failure
                        log.critical("LAB MODE — Camera connection failed after %d attempts (including power cycle). MANUAL INTERVENTION REQUIRED.", max_retries + 1)
                        log.critical("LAB MODE — Check: 1) Camera physically connected via USB, 2) Camera powered on, 3) gphoto2 --auto-detect works")
                        self._lab_relay_on = False  # Force re-init on next tick
                        break

        # ── Health Check: Monitor frame_push and camera responsiveness ─────────────
        if getattr(self, "_lab_relay_on", False) and _FRAME_PUSH_AVAILABLE:
            # Check if frame_push is actually running when it should be
            if self._live_frame_enabled:
                if frame_push_is_running and not frame_push_is_running():
                    log.warning("LAB MODE — Health check: frame_push stopped unexpectedly!")
                    # Try to restart it
                    self._live_frame_enabled = False  # Reset flag to allow restart
                    try:
                        if start_frame_push(self._device_id, self._api, self._driver):
                            self._live_frame_enabled = True
                            log.info("LAB MODE — Frame push restarted after health check")
                        else:
                            # Frame push failed - camera might be in bad state
                            log.error("LAB MODE — Frame push restart failed, camera may need power cycle")
                            # Track consecutive failures
                            failures = getattr(self, "_lab_health_failures", 0) + 1
                            self._lab_health_failures = failures
                            if failures >= 3:
                                log.warning("LAB MODE — Too many health failures, power cycling camera")
                                self._lab_relay_on = False  # Force re-init on next tick
                                self._lab_health_failures = 0
                    except Exception as exc:
                        log.warning("LAB MODE — Frame push restart error: %s", exc)
                else:
                    # Reset failure counter on successful health check
                    self._lab_health_failures = 0

        if ok and cfg_data:
            # Check if lab mode has been disabled
            if not cfg_data.get("debug_mode", {}).get("enabled", False):
                log.info("LAB MODE — disabled from headend, exiting lab mode")

                # Stop Frame Push if running
                if _FRAME_PUSH_AVAILABLE and self._live_frame_enabled:
                    try:
                        stop_frame_push()
                        self._live_frame_enabled = False
                        log.info("LAB MODE — Frame push stopped")
                        # Reconnect driver after frame push stops
                        try:
                            self._driver.connect()
                            log.debug("LAB MODE — Driver reconnected after frame push")
                        except Exception as exc:
                            log.warning("LAB MODE — Driver reconnect failed: %s", exc)
                    except Exception as exc:
                        log.warning("LAB MODE — Frame push stop error: %s", exc)

                try:
                    self._driver.disconnect()
                except Exception as exc:
                    log.warning("LAB MODE — camera disconnect after disable failed: %s", exc)
                self._camera_power_off("lab disabled", force=True)
                self._lab_relay_on = False
                if getattr(self, "_service_platform", None):
                    self._service_platform.invalidate(reason="lab_disabled")
                # Save updated config
                self._cfg_mgr.save_config(cfg_data)
                self._cfg = self._cfg_mgr.load()
                self._uploader.update_config(cfg_data)
                self._last_config_pull = datetime.now(timezone.utc)
                return
            lab_cmd      = cfg_data.get("lab_command", {})
            pending_params = cfg_data.get("pending_params", [])

            # Apply pending parameter changes
            for param in pending_params:
                try:
                    self._driver.set_config(param["key"], param["value"])
                    log.info("LAB — set %s = %s", param["key"], param["value"])
                except Exception as exc:
                    log.warning("LAB — set_config failed: %s = %s: %s", param["key"], param["value"], exc)
            # Clear pending params on headend
            if pending_params:
                _, resp = self._api.clear_lab_params(self._device_id)
                self._check_config_version(resp)

            # Execute lab command
            cmd_type = lab_cmd.get("type")
            if cmd_type == "preview":
                self._lab_stop_frame_push()  # Stop before preview
                try:
                    self._lab_capture_preview()
                finally:
                    self._lab_start_frame_push()  # Restart after preview
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)
            elif cmd_type == "capture":
                log.info("LAB — full capture requested — stopping frame push before cycle")
                # Stop frame push FIRST to avoid gphoto2 conflicts
                self._lab_stop_frame_push()
                # Disconnect og frigiv kamera INDEN _do_capture_cycle kaldes.
                # _do_capture_cycle forventer at kameraet IKKE er forbundet —
                # den laver selv power-mode handling -> connect -> capture -> disconnect.
                # Dobbelt-connect på et allerede tilsluttet gphoto2-kamera fejler stille.
                try:
                    self._driver.disconnect()
                except Exception:
                    pass
                self._camera_power_off("lab full capture handoff")
                self._lab_relay_on = False          # tvinger re-init på næste tick
                ok = self._do_capture_cycle()
                result = {
                    "type": "capture",
                    "command_id": lab_cmd.get("command_id"),
                    "ok": bool(ok),
                    **(getattr(self, "_last_capture_result", None) or {}),
                }
                capture_path = Path(str(result.get("filepath") or ""))
                if capture_path.is_file() and capture_path.suffix.lower() in {".jpg", ".jpeg"}:
                    try:
                        lab_dir = Path("/data/captures/_lab")
                        lab_dir.mkdir(parents=True, exist_ok=True)
                        preview_name = f"preview_capture_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}{capture_path.suffix.lower()}"
                        preview_path = lab_dir / preview_name
                        shutil.copy2(capture_path, preview_path)
                        upload_ok, _ = self._api.upload_lab_preview(preview_path)
                        if upload_ok:
                            result["preview_filename"] = preview_path.name
                    except Exception as exc:
                        result["preview_error"] = str(exc)
                # Note: Frame push will restart on next _lab_tick when camera is ready again
                self._api._post("/lab/" + self._device_id + "/result", result)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)
                # _lab_relay_on er allerede False — næste _lab_tick re-initialiserer
                # relay + connect + camera-ready signal automatisk

            elif cmd_type == "get_params":
                log.info("LAB — fetching all camera params")
                self._lab_stop_frame_push()  # Stop before accessing camera
                try:
                    # Reconnect driver for get_params
                    self._driver.connect()
                    params = self._driver.get_all_config()
                    profile = {}
                    if hasattr(self._driver, "get_profile_summary"):
                        profile = self._driver.get_profile_summary()
                    self._api._post("/lab/" + self._device_id + "/params", {
                        "params": params,
                        "profile": profile,
                    })
                    log.info("LAB — sent %d params to headend", len(params))
                except Exception as exc:
                    log.warning("LAB — get_params failed: %s", exc)
                finally:
                    self._lab_start_frame_push()  # Restart after get_params
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            elif cmd_type == "set_param":
                key = lab_cmd.get("key", "")
                value = lab_cmd.get("value", "")
                log.info("LAB — set param: %s = %s", key, value)
                result = {
                    "type": "set_param",
                    "command_id": lab_cmd.get("command_id"),
                    "key": key,
                    "value": value,
                    "ok": False,
                }
                self._lab_stop_frame_push()  # Stop before accessing camera
                try:
                    # Reconnect driver for set_param
                    self._driver.connect()
                    self._driver.set_config(key, value)
                    result["ok"] = True
                    result["param"] = self._driver.get_config_param(key) if hasattr(self._driver, "get_config_param") else None
                    params = self._driver.get_all_config()
                    profile = self._driver.get_profile_summary() if hasattr(self._driver, "get_profile_summary") else {}
                    self._api._post("/lab/" + self._device_id + "/params", {
                        "params": params,
                        "profile": profile,
                    })
                except Exception as exc:
                    result["error"] = str(exc)
                    log.warning("LAB — set_param failed: %s", exc)
                finally:
                    self._lab_start_frame_push()  # Restart after set_param
                self._api._post("/lab/" + self._device_id + "/result", result)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            elif cmd_type == "focus_drive":
                value = lab_cmd.get("value", "")
                log.info("LAB — focus drive: %s", value)
                result = {
                    "type": "focus_drive",
                    "command_id": lab_cmd.get("command_id"),
                    "value": value,
                    "ok": False,
                }
                self._lab_stop_frame_push()  # Stop before focus operation
                try:
                    # Reconnect driver for focus operation
                    self._driver.connect()
                    if hasattr(self._driver, "drive_manual_focus"):
                        result["ok"] = bool(self._driver.drive_manual_focus(value))
                    if result["ok"]:
                        preview = self._lab_capture_preview()
                        if preview:
                            result["quality"] = self._lab_quality_summary(preview)
                            result["preview_filename"] = preview.name
                except Exception as exc:
                    result["error"] = str(exc)
                    log.warning("LAB — focus drive failed: %s", exc)
                finally:
                    self._lab_start_frame_push()  # Restart after focus operation
                self._api._post("/lab/" + self._device_id + "/result", result)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            elif cmd_type == "autofocus":
                log.info("LAB — autofocus requested")
                result = {
                    "type": "autofocus",
                    "command_id": lab_cmd.get("command_id"),
                    "ok": False,
                }
                self._lab_stop_frame_push()  # Stop before autofocus
                try:
                    # Reconnect driver for autofocus
                    self._driver.connect()
                    result["ok"] = bool(self._driver.run_autofocus())
                    preview = self._lab_capture_preview()
                    if preview:
                        result["quality"] = self._lab_quality_summary(preview)
                        result["preview_filename"] = preview.name
                except Exception as exc:
                    result["error"] = str(exc)
                    log.warning("LAB — autofocus failed: %s", exc)
                finally:
                    self._lab_start_frame_push()  # Restart after autofocus
                self._api._post("/lab/" + self._device_id + "/result", result)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            elif cmd_type in ("focus_slice", "edge_ai_focus_test"):
                log.info("LAB — %s requested", cmd_type)
                self._lab_stop_frame_push()  # Stop before focus slice
                try:
                    # Reconnect driver for focus slice
                    self._driver.connect()
                    result = self._lab_focus_slice(
                        step_value=lab_cmd.get("step_value", ""),
                        count=int(lab_cmd.get("count", 5)),
                        run_autofocus_first=bool(lab_cmd.get("run_autofocus_first", True)),
                        result_type=cmd_type,
                    )
                    result["command_id"] = lab_cmd.get("command_id")
                finally:
                    self._lab_start_frame_push()  # Restart after focus slice
                self._api._post("/lab/" + self._device_id + "/result", result)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            elif cmd_type == "live_stream":
                enabled = bool(lab_cmd.get("enabled"))
                result = {
                    "type": "live_stream",
                    "command_id": lab_cmd.get("command_id"),
                    "enabled": enabled,
                    "ok": False,
                }
                if not _FRAME_PUSH_AVAILABLE:
                    result["error"] = "Frame push module is unavailable on this Edge"
                elif enabled:
                    # A separate gphoto2 process owns the camera while movie
                    # capture is active; release the normal driver first.
                    self._live_frame_enabled = True
                    self._lab_start_frame_push()
                    result["ok"] = bool(frame_push_is_running and frame_push_is_running())
                    if not result["ok"]:
                        result["error"] = "Could not start camera movie stream"
                else:
                    self._lab_stop_frame_push()
                    self._live_frame_enabled = False
                    result["ok"] = not bool(frame_push_is_running and frame_push_is_running())
                    if not result["ok"]:
                        result["error"] = "Could not stop camera movie stream"
                self._api._post("/lab/" + self._device_id + "/result", result)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            elif cmd_type == "relay_toggle":
                relay = lab_cmd.get("relay", "camera")
                state = lab_cmd.get("state", False)
                log.info("LAB — relay toggle: %s → %s", relay, "ON" if state else "OFF")
                try:
                    if relay == "camera":
                        if state:
                            self._relay.camera.power_on()
                        else:
                            self._relay.camera.force_off()
                    elif relay == "modem":
                        if state:
                            self._relay.modem.power_on()
                        else:
                            self._relay.modem.power_cycle(reason="manual OFF")
                except Exception as exc:
                    log.warning("LAB — relay toggle failed: %s", exc)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            elif cmd_type == "wifi_scan":
                log.info("LAB — WiFi scan")
                try:
                    from diagnostics.wifi import scan, status, list_saved
                    networks = scan()
                    current  = status()
                    saved    = list_saved()
                    self._api._post("/lab/" + self._device_id + "/wifi/result", {
                        "type": "scan", "networks": networks,
                        "current": current, "saved": saved,
                    })
                    log.info("LAB — WiFi scan: %d netvaerk", len(networks))
                except Exception as exc:
                    log.warning("LAB — WiFi scan failed: %s", exc)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            elif cmd_type == "wifi_connect":
                ssid     = lab_cmd.get("ssid", "")
                password = lab_cmd.get("password", "")
                log.info("LAB — WiFi connect: %s", ssid)
                try:
                    from diagnostics.wifi import connect, status
                    result  = connect(ssid, password)
                    current = status()
                    self._api._post("/lab/" + self._device_id + "/wifi/result", {
                        "type": "connect", "result": result, "current": current,
                    })
                except Exception as exc:
                    log.warning("LAB — WiFi connect failed: %s", exc)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            elif cmd_type == "wifi_forget":
                ssid = lab_cmd.get("ssid", "")
                log.info("LAB — WiFi forget: %s", ssid)
                try:
                    from diagnostics.wifi import forget
                    result = forget(ssid)
                    self._api._post("/lab/" + self._device_id + "/wifi/result", {
                        "type": "forget", "result": result,
                    })
                except Exception as exc:
                    log.warning("LAB — WiFi forget failed: %s", exc)
                _, resp = self._api.clear_lab_command(self._device_id)
                self._check_config_version(resp)

            # ── Frame Push Live View (F-013C) ───────────────────────────────────────────
            # Frame push kører automatisk når LAB mode er aktiv.
            # Edge pushes frames til headend via /api/lab/{id}/live-frame.
            # Browser polls frames fra headend via /api/lab/{id}/live-frame.

        time.sleep(poll_s)

    # ── Frame Push Management Helpers (LAB mode) ─────────────────────────────────────

    def _lab_stop_frame_push(self) -> None:
        """Stop frame push before camera operations to avoid gphoto2 conflicts."""
        if _FRAME_PUSH_AVAILABLE and self._live_frame_enabled:
            try:
                # Check if actually running before stopping
                if frame_push_is_running and frame_push_is_running():
                    stop_frame_push()
                    # Wait for gphoto2 to fully release camera (terminate() is async)
                    time.sleep(1.0)
                    log.info("LAB — Frame push stopped for camera operation")
            except Exception as exc:
                log.warning("LAB — Frame push stop failed: %s", exc)

    def _lab_start_frame_push(self) -> None:
        """Start/restart frame push after camera operations."""
        if _FRAME_PUSH_AVAILABLE and self._live_frame_enabled:
            try:
                # Only start if user enabled it AND it's not already running
                if not frame_push_is_running or not frame_push_is_running():
                    # Disconnect driver to free camera for gphoto2 --capture-movie
                    try:
                        self._driver.disconnect()
                        log.debug("LAB — Driver disconnected for frame push restart")
                    except Exception:
                        pass
                    # Start frame push (uses own gphoto2 instance)
                    if start_frame_push(self._device_id, self._api, self._driver):
                        log.info("LAB — Frame push restarted")
            except Exception as exc:
                log.warning("LAB — Frame push restart failed: %s", exc)

    def _check_config_version(self, api_resp: dict | None) -> None:
        """Check if config version changed in API response and trigger pull if needed."""
        if not isinstance(api_resp, dict):
            return
        resp_version = api_resp.get("config_version", "")
        if not resp_version:
            return
        current_version = self._cfg.get("config_version", "")
        if resp_version != current_version:
            log.info("Config version ændret via API — henter ny config (%s→%s)",
                     current_version[:8] if current_version else "none",
                     resp_version[:8])
            self._pull_config()

    # ── Lab Quality Summary ───────────────────────────────────────────────────────

    def _lab_quality_summary(self, filepath: Path) -> dict:
        """Run local deterministic image-quality analysis for LAB focus work."""
        try:
            if hasattr(self._quality, "qa_report"):
                return self._quality.qa_report(filepath)
            return self._quality.check(filepath).as_dict()
        except Exception as exc:
            return {"flag": "error", "passed": False, "message": str(exc)}

    def _lab_focus_slice(
        self,
        step_value: str,
        count: int = 5,
        run_autofocus_first: bool = True,
        result_type: str = "focus_slice",
    ) -> dict:
        """Capture a small focus slice series and score sharpness locally."""
        count = max(1, min(12, int(count or 5)))
        result = {
            "type": result_type,
            "step_value": step_value,
            "count": count,
            "ok": False,
            "frames": [],
            "recommendation": {},
            "analysis_engine": "opencv_laplacian_brightness",
        }
        if not step_value:
            result["error"] = "step_value missing"
            return result
        try:
            if run_autofocus_first and self._driver.supports_autofocus():
                result["autofocus_ok"] = bool(self._driver.run_autofocus())
                time.sleep(0.5)

            best = None
            for idx in range(count):
                if idx > 0:
                    if hasattr(self._driver, "drive_manual_focus"):
                        self._driver.drive_manual_focus(step_value)
                    time.sleep(0.35)
                preview = self._lab_capture_preview()
                if not preview:
                    continue
                quality = self._lab_quality_summary(preview)
                frame = {
                    "index": idx,
                    "step_value": step_value if idx > 0 else "baseline",
                    "preview_filename": preview.name,
                    "quality": quality,
                }
                result["frames"].append(frame)
                blur = quality.get("blur_score")
                if blur is not None and (best is None or blur > best["quality"].get("blur_score", -1)):
                    best = frame

            result["ok"] = len(result["frames"]) > 0
            if best:
                result["recommendation"] = {
                    "best_index": best["index"],
                    "best_preview_filename": best["preview_filename"],
                    "best_blur_score": best["quality"].get("blur_score"),
                    "message": "Best frame is a recommendation only; focus is not auto-applied.",
                }
        except Exception as exc:
            result["error"] = str(exc)
            log.warning("LAB — focus slice failed: %s", exc)
        return result

    def _lab_capture_preview(self):
        """Capture a preview image and upload to _lab directory."""
        try:
            dest_dir = Path("/data/captures/_lab")
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Disconnect first if needed (preview needs clean USB state)
            try:
                self._driver.disconnect()
            except Exception:
                pass
            time.sleep(0.5)
            self._driver.connect()

            preview_path = self._driver.capture_preview(dest_dir)
            log.info("LAB — preview: %s (%d KB)",
                     preview_path.name, preview_path.stat().st_size // 1024)

            ok, _ = self._api.upload_lab_preview(preview_path)
            if ok:
                return preview_path

            # Fallback: upload to headend via SFTP to _lab directory.
            sftp_cfg = self._cfg.get("sftp", {})
            if sftp_cfg.get("host"):
                ssh  = None
                sftp = None
                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(
                        sftp_cfg["host"],
                        port     = int(sftp_cfg.get("port", 22)),
                        username = sftp_cfg["username"],
                        password = sftp_cfg.get("password", ""),
                        timeout  = int(self._cfg.get("system", {}).get("api_timeout_s", 15)),
                    )
                    sftp = ssh.open_sftp()
                    remote_dir = str(
                        PurePosixPath(sftp_cfg.get("remote_base", "/incoming"))
                        / "_lab" / self._device_id
                    )
                    current = ""
                    for part in remote_dir.split("/"):
                        if not part:
                            continue
                        current += "/" + part
                        try:
                            sftp.stat(current)
                        except FileNotFoundError:
                            try:
                                sftp.mkdir(current)
                            except Exception:
                                pass
                    sftp.put(str(preview_path), remote_dir + "/" + preview_path.name)
                    log.info("LAB — preview uploaded to %s", remote_dir)
                    return preview_path
                finally:
                    if sftp:
                        try: sftp.close()
                        except Exception: pass
                    if ssh:
                        try: ssh.close()
                        except Exception: pass
        except Exception as exc:
            log.warning("LAB — preview failed: %s", exc)
        return None

    # ── Shutdown ────────────────────────────────────────────────────────────

    def _shutdown(self) -> None:
        log.info("Shutting down edge agent…")
        if self._site_look_config_client is not None:
            try:
                self._site_look_config_client.stop_polling()
            except Exception as exc:
                log.warning("Site Look config poller stop failed: %s", exc)
        tunnel = getattr(self, "_tunnel", None)
        if tunnel is not None:
            try:
                tunnel.stop()
            except Exception as exc:
                log.warning("SSH tunnel manager stop failed: %s", exc)
        # Ensure lab relay is OFF if we were in lab mode
        if getattr(self, "_lab_relay_on", False):
            log.info("Shutdown: releasing lab camera")
            try:
                self._driver.disconnect()
            except Exception:
                pass
            try:
                self._camera_power_off("shutdown", force=True)
            except Exception:
                pass
            self._lab_relay_on = False
        try:
            self._relay.cleanup(camera=self._camera_uses_relay())
        except Exception:
            pass
        self._send_heartbeat(check_updates=False)
        log.info("Edge agent stopped.")

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_time(t: str):
        """Parse 'HH:MM' string to time object."""
        from datetime import time as dt_time
        h, m = t.split(":")
        return dt_time(int(h), int(m))

    @staticmethod
    def _to_local(dt: datetime, tz_name: str) -> datetime:
        """Convert UTC datetime to local timezone."""
        try:
            from zoneinfo import ZoneInfo
            return dt.astimezone(ZoneInfo(tz_name))
        except Exception:
            return dt   # fall back to UTC


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TimeLapse Pro Edge Agent")
    parser.add_argument("--single-capture", action="store_true",
                        help="Run one capture cycle and exit")
    parser.add_argument("--debug",          action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--config-dir",     type=str, default=None,
                        help="Override config directory path")
    args = parser.parse_args()

    setup_logging(args.debug)

    # Load config
    base_dir = Path(args.config_dir) if args.config_dir else None
    cfg_mgr  = ConfigManager(base_dir)
    try:
        config = cfg_mgr.load()
    except FileNotFoundError as exc:
        log.critical("Cannot start: %s", exc)
        sys.exit(1)

    agent = EdgeAgent(config, cfg_mgr)

    if args.single_capture:
        success = agent.run_single_capture()
        sys.exit(0 if success else 1)
    else:
        agent.run()


if __name__ == "__main__":
    main()
