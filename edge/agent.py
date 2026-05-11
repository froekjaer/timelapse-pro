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
import logging
import os
import signal
import sys
import threading
import time
import paramiko
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

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
try:
    from tunnel.ssh_manager import SshTunnelManager
    _SSH_TUNNEL_AVAILABLE = True
except ImportError:
    _SSH_TUNNEL_AVAILABLE = False
from utils.database         import EdgeDatabase

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
        self._quality      = QualityChecker(config)
        self._buffer       = CircularBuffer(config)
        self._diag         = DiagnosticsCollector(config)
        self._uploader     = UploadManager(config, self._db)
        self._api          = HeadendClient(config, config_manager)
        self._connectivity = self._relay.connectivity      # modem auto-cycle monitor

        # State
        self._last_heartbeat:  datetime = datetime.min.replace(tzinfo=timezone.utc)
        self._last_config_pull:datetime = datetime.min.replace(tzinfo=timezone.utc)

        # Signal handling for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT,  self._handle_signal)

        log.info("EdgeAgent initialised — device_id=%s", self._device_id)

    def _handle_signal(self, signum, frame):
        log.info("Signal %d received — shutting down gracefully…", signum)
        self._running = False

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
                        log.info("LAB MODE — exiting, relay OFF")
                        try: self._driver.disconnect()
                        except: pass
                        self._relay.camera.force_off()
                        self._lab_relay_on = False
                    self._tick(mode)
            except Exception as exc:
                log.exception("Unhandled error in main loop: %s", exc)
                self._db.log_event(
                    self._device_id, "ERROR", "system",
                    f"Unhandled loop error: {exc}"
                )
                time.sleep(int(self._cfg.get("system", {}).get("error_recovery_sleep_s", 30)))

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

        # 2. Send startup heartbeat
        self._send_heartbeat()

        # CMDB: rapportér hardwareinventar til headend (ikke-blokerende)
        try:
            from utils.inventory import report_inventory
            report_inventory(self._cfg, self._api)
        except Exception as _inv_exc:
            import logging as _log
            _log.getLogger(__name__).warning("Inventar-rapportering fejlede: %s", _inv_exc)

                # SSH tunnel manager (Sprint C)
        self._tunnel = None
        if _SSH_TUNNEL_AVAILABLE:
            try:
                self._tunnel = SshTunnelManager(self._cfg, self._api)
                self._tunnel.start()
                log.info("SSH tunnel manager initialiseret")
            except Exception as exc:
                log.warning("SSH tunnel manager fejl: %s", exc)

        # 3. Detect camera features (once per session)
        self._load_camera_features()

        # 3b. Auto-bootstrap sibling kameraer
        self._auto_bootstrap_cameras()

        # 4. Retry any pending uploads from before last reboot
        camera_id = self._cfg.get("device", {}).get("device_id", "unknown")
        retry_results = self._uploader.retry_pending(camera_id)
        if any(v > 0 for v in retry_results.values()):
            log.info("Startup upload retry: %s", retry_results)

        # 5. Sync unsynced capture records to headend
        self._sync_captures()

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
            quality = self._quality.check(result.filepath, result.sha256)
            self._db.insert_capture(
                device_id=device_id, filepath=result.filepath,
                sha256=result.sha256, captured_at=result.timestamp,
                camera_model=result.camera_model, driver_name=result.driver_name,
                filesize=result.filesize, exposure_time=result.exposure_time,
                aperture=result.aperture, iso=result.iso, focus_mode=result.focus_mode,
                quality_flag=quality.flag.value, quality_passed=quality.passed,
                blur_score=quality.blur_score, brightness=quality.brightness_mean,
            )
            upload = self._uploader.upload_capture(None, result.filepath, device_id)
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
        self._send_heartbeat()
        self._sync_captures()
        return ok > 0

    def _load_camera_features(self) -> None:
        """Detect camera capabilities for this session."""
        try:
            self._relay.camera.power_on()
            self._driver.connect()
            self._has_autofocus = self._driver.supports_autofocus()
            self._has_refocus   = self._driver.supports_remote_focus()
            self._driver.disconnect()
            self._relay.camera.power_off()
            log.info(
                "Camera features: autofocus=%s remote_focus=%s",
                self._has_autofocus, self._has_refocus
            )
        except Exception as exc:
            log.warning("Could not detect camera features: %s", exc)
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

        # Periodic config re-pull (every 6 hours)
        config_interval = timedelta(minutes=int(
            self._cfg.get("diagnostics", {}).get("config_poll_interval_minutes", 5)
        ))
        if now - self._last_config_pull > config_interval:
            self._pull_config()
            # Tjek om headend har bedt om en opdatering
            self._check_update()

        # Check capture schedule
        if self._should_capture(now, mode):
            node_cameras = self._cfg.get('node_cameras', [])
            multi_mode   = self._cfg.get('multi_camera_mode', 'single')
            if node_cameras and multi_mode in ('auto_bootstrap', 'manual'):
                cameras = self._discover_cameras()
                if len(cameras) > 1:
                    self._do_multi_capture_cycle(cameras)
                else:
                    log.info("Kun %d kamera fundet — single mode", len(cameras))
                    self._do_capture_cycle()
            else:
                self._do_capture_cycle()

        # Heartbeat (every 60 minutes)
        heartbeat_interval = timedelta(minutes=int(
            self._cfg.get("diagnostics", {}).get("heartbeat_interval_minutes", 60)
        ))
        if now - self._last_heartbeat > heartbeat_interval:
            self._send_heartbeat()
            self._sync_captures()

        # Calculate sleep until next event
        sleep_s = self._seconds_until_next_event(now, mode)

        if sleep_s > 60:
            log.info("Sleeping %ds until next capture…", sleep_s)
        time.sleep(min(sleep_s, 60))   # wake at least every 60s to check signals

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

        try:
            # 1. Power camera on and connect
            self._relay.camera.power_on()
            try:
                self._driver.connect()
            except Exception as exc:
                log.error("Camera connect failed: %s", exc)
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
            quality = self._quality.check(result.filepath, None)  # sha256 pre-XMP — skip disk re-verify
            if not quality.passed:
                log.warning("Quality FAILED: %s — %s", result.filepath.name, quality.message)
            else:
                log.info("Quality OK: %s", quality.message)

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
                quality_flag = quality.flag.value,
                quality_passed=quality.passed,
                blur_score   = quality.blur_score,
                brightness   = quality.brightness_mean,
            )

            # 7. Enforce circular buffer BEFORE upload (free space first)
            self._buffer.enforce(self._db)

            # 8. Upload — report connectivity result
            camera_id      = self._cfg.get("device", {}).get("device_id", "unknown")
            upload_results = self._uploader.upload_capture(
                capture_id, result.filepath, camera_id
            )
            log.info("Upload results: %s", upload_results)

            if upload_results.get("primary"):
                self._connectivity.report_success()
            else:
                self._connectivity.report_failure()

            # Camera diagnostics while relay is still ON
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
                self._last_cam_diag = collect_camera_diagnostics(cam_model, expected)
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

            # Send heartbeat immediately after capture with fresh camera diagnostics
            self._send_heartbeat()
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
            self._relay.camera.power_off()

        log.info("─── Capture cycle complete (success=%s) ───", success)
        return success

    # ── Scheduling ──────────────────────────────────────────────────────────

    def _should_capture(self, now: datetime, mode: str) -> bool:
        """Return True if relay should power ON now (warmup-adjusted)."""
        schedule = self._cfg.get("schedule", {})
        warmup_s = int(self._cfg.get("camera", {}).get("relay_on_seconds_before", 10))
        lead_s   = warmup_s + 3
        active_hours = schedule.get("active_hours")
        if active_hours and len(active_hours) == 2:
            tz_name   = schedule.get("timezone", "UTC")
            local_now = self._to_local(now, tz_name)
            start_t   = self._parse_time(active_hours[0])
            end_t     = self._parse_time(active_hours[1])
            if not (start_t <= local_now.time() <= end_t):
                return False
        if mode == "interval":
            interval_s   = int(schedule.get("interval_minutes", 60)) * 60
            epoch_s      = int(now.timestamp())
            pos_in_cycle = epoch_s % interval_s
            return (interval_s - pos_in_cycle) <= lead_s
        if mode == "fixed":
            tz_name   = schedule.get("timezone", "UTC")
            local_now = self._to_local(now, tz_name)
            for t_str in schedule.get("capture_times", []):
                try:
                    h, m   = map(int, t_str.split(":"))
                    target = local_now.replace(hour=h, minute=m, second=0, microsecond=0)
                    diff   = (target - local_now).total_seconds()
                    if lead_s - 2 <= diff <= lead_s + 2:
                        return True
                except Exception:
                    pass
        return False

    def _seconds_until_next_event(self, now: datetime, mode: str) -> int:
        """Calculate seconds until next capture or heartbeat."""
        schedule      = self._cfg.get("schedule", {})
        warmup_s      = int(self._cfg.get("camera", {}).get("relay_on_seconds_before", 10))
        lead_s        = warmup_s + 3
        heartbeat_min = int(self._cfg.get("diagnostics", {}).get("heartbeat_interval_minutes", 60))
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

    # ── Headend communication ───────────────────────────────────────────────

    def _pull_config(self) -> None:
        """Fetch and apply updated config from headend."""
        old_version = self._cfg.get("config_version", "")
        ok, data = self._api.fetch_config()
        if ok and data:
            try:
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
        else:
            log.info("Config pull failed — using cached config")
        self._last_config_pull = datetime.now(timezone.utc)

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
            value = cam_cfg.get(cfg_key)
            if value is None:
                continue
            # Erstat eksisterende kommando eller tilføj ny
            prefix = f"{gphoto_key}="
            new_cmd = f"{gphoto_key}={value}"
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

    def _check_update(self) -> None:
        """Tjek om headend har bedt om en edge opdatering."""
        import subprocess, os
        update_requested = self._cfg.get("update_requested", False)
        if not update_requested:
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



    def _collect_update_info(self) -> dict:
        """Saml OS opdateringsinfo og git commit. Ingen internet nødvendig."""
        info = {"os_security_count": 0, "os_updates_count": 0, "app_version": "ukendt"}

        # OS opdateringer — læs pakkeliste fra apt
        try:
            import subprocess as _sp2
            r2 = _sp2.run(["apt", "list", "--upgradable"],
                         capture_output=True, text=True, timeout=15)
            lines = [l for l in r2.stdout.splitlines() if "/" in l]
            security_pkgs = [l.split("/")[0] for l in lines if "security" in l.lower()]
            other_pkgs    = [l.split("/")[0] for l in lines if "security" not in l.lower()]
            info["os_security_count"]    = len(security_pkgs)
            info["os_updates_count"]     = len(other_pkgs)
            info["os_security_packages"] = security_pkgs[:50]
            info["os_update_packages"]   = other_pkgs[:50]
            info["os_distro"]            = "noble"
            info["os_arch"]              = "arm64"
        except Exception as e:
            log.debug("apt list fejl: %s", e)

        # App version — git commit hash
        try:
            import os as _os, subprocess as _sub
            repo = Path(_os.getenv('TIMELAPSE_REPO_DIR', '/opt/timelapse'))
            r = _sub.run(
                ["/usr/bin/git", "-c", "safe.directory=/opt/timelapse", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and r.stdout.strip():
                info["app_version"] = r.stdout.strip()[:7]
        except Exception as e:
            log.debug("git rev-parse fejl: %s", e)

        return info


    def _check_and_apply_updates(self) -> None:
        """Tjek om der er godkendte opdateringer og eksekvér dem."""
        log.info("Update-check: starter...")
        try:
            ok, policy = self._api._get(f"/updates/policy/{self._device_id}")
            if not ok or not policy:
                return
            pending = policy.get("pending_updates", [])
            if not pending:
                return

            for update in pending:
                uid    = update["id"]
                utype  = update["update_type"]
                status = update["status"]

                if status == "rollback_requested":
                    log.info("Rollback anmodet for opdatering %d (%s)", uid, utype)
                    self._run_rollback(uid)
                    return

                if status == "approved":
                    log.info("Udfører opdatering %d: %s", uid, utype)
                    self._run_update(uid, utype)
                    return  # Ét ad gangen

        except Exception as e:
            log.warning("Update-check fejl: %s", e, exc_info=True)

    def _run_update(self, update_id: int, update_type: str) -> None:
        """Kør opdatering baseret på type og rapportér resultat."""
        import subprocess as _sp, os as _os

        if update_type in ("os_security", "os_updates"):
            # OS opdateringer via apt — kræver sudo
            log.info("OS opdatering %d: kører apt upgrade (sikker, non-interactive)", update_id)
            env = {**_os.environ, "DEBIAN_FRONTEND": "noninteractive"}
            result = _sp.run(
                ["sudo", "apt-get", "upgrade", "-y", "--only-upgrade",
                 "-o", "dir::cache=/data/apt-cache",
                 "-o", "Dpkg::Options::=--force-confdef",
                 "-o", "Dpkg::Options::=--force-confold"],

                capture_output=True, text=True, timeout=600, env=env
            )
        else:
            # App opdateringer via git pull (edge_update.sh)
            script = Path("/opt/timelapse/deploy/edge_update.sh")
            if not script.exists():
                log.warning("edge_update.sh ikke fundet")
                self._api._post("/updates/report", {"update_id": update_id, "status": "rolled_back"})
                return
            env = {**_os.environ, "UPDATE_TYPE": update_type, "UPDATE_ID": str(update_id)}
            result = _sp.run(["bash", str(script)], capture_output=True, text=True, timeout=300, env=env)

        if result.returncode == 0:
            log.info("Opdatering %d gennemført OK", update_id)
            self._api._post("/updates/report", {"update_id": update_id, "status": "deployed"})
        else:
            log.warning("Opdatering %d fejlede (rc=%d)\n%s", update_id, result.returncode, result.stderr[-300:])
            self._api._post("/updates/report", {"update_id": update_id, "status": "rolled_back"})

    def _run_rollback(self, update_id: int) -> None:
        """Tving rollback til forrige version."""
        import subprocess as _sp
        prev = Path("/opt/timelapse/prev")
        if not prev.exists():
            log.warning("Ingen forrige version til rollback")
            self._api._post("/updates/report", {"update_id": update_id, "status": "rolled_back"})
            return
        _sp.run(["bash", "-c", f"cp -r {prev}/* /opt/timelapse/"], timeout=60)
        log.info("Rollback til forrige version gennemført")
        self._api._post("/updates/report", {"update_id": update_id, "status": "rolled_back"})

    def _send_heartbeat(self) -> None:
        """Collect diagnostics and send heartbeat to headend."""
        try:
            diag_data     = self._diag.collect()
            capture_stats = self._db.capture_stats(self._device_id)
            self._db.insert_diagnostics(self._device_id, diag_data)

            # Include last camera diagnostics from capture cycle
            if hasattr(self, "_last_cam_diag") and self._last_cam_diag:
                diag_data["camera"] = self._last_cam_diag

            diag_data["updates"] = self._collect_update_info()
            ok, _ = self._api.send_heartbeat(diag_data, capture_stats)
            if ok:
                log.info("Heartbeat sent OK")
                self._connectivity.report_success()
                # Tjek om config er ændret siden sidst
                hb_version = (_ or {}).get("config_version", "") if isinstance(_, dict) else ""
                if hb_version and hb_version != self._cfg.get("config_version", ""):
                    log.info("Config version ændret via heartbeat — henter ny config")
                    self._pull_config()
            else:
                log.warning("Heartbeat failed — headend unreachable")
                self._connectivity.report_failure()
        except Exception as exc:
            log.warning("Heartbeat error: %s", exc)
            self._connectivity.report_failure()
        finally:
            self._last_heartbeat = datetime.now(timezone.utc)
            self._check_and_apply_updates()

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

    # ── Lab / debug mode ────────────────────────────────────────────────────

    def _lab_tick(self, debug_cfg: dict) -> None:
        """
        Lab mode tick — relay stays ON, polls for commands from headend.
        Supports: preview capture, full capture, set-param, relay toggle.
        Poll interval: debug_cfg.config_poll_s (default 1 second).
        """
        poll_s = int(debug_cfg.get("config_poll_s", 1))

        # Ensure relay is ON
        if not getattr(self, "_lab_relay_on", False):
            log.info("LAB MODE — relay ON permanent")
            self._relay.camera.power_on()
            self._lab_relay_on = True
            time.sleep(int(self._cfg.get("camera", {}).get("relay_on_seconds_before", 10)))
            try:
                self._driver.connect()
                commands = self._build_camera_commands()
                if commands:
                    self._driver.apply_initial_commands(commands)
                log.info("LAB MODE — camera connected and ready")
                # Signal til headend at kamera er klar
                try:
                    self._api._post("/lab/" + self._device_id + "/camera-ready", {"ready": True})
                except Exception:
                    pass
            except Exception as exc:
                log.warning("LAB MODE — camera connect failed: %s", exc)

        # Pull config for pending commands
        ok, cfg_data = self._api.fetch_config()
        if ok and cfg_data:
            # Check if lab mode has been disabled
            if not cfg_data.get("debug_mode", {}).get("enabled", False):
                log.info("LAB MODE — disabled from headend, exiting lab mode")
                try: self._driver.disconnect()
                except: pass
                self._relay.camera.force_off()
                self._lab_relay_on = False
                # Save updated config
                self._cfg_mgr.save_config(cfg_data)
                self._cfg = self._cfg_mgr.load()
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
                self._api.clear_lab_params(self._device_id)

            # Execute lab command
            cmd_type = lab_cmd.get("type")
            if cmd_type == "preview":
                self._lab_capture_preview()
                self._api.clear_lab_command(self._device_id)
            elif cmd_type == "capture":
                log.info("LAB — full capture requested — disconnecting before cycle")
                # Disconnect og sluk relay INDEN _do_capture_cycle kaldes.
                # _do_capture_cycle forventer at kameraet IKKE er forbundet —
                # den laver selv power_on -> connect -> capture -> disconnect -> power_off.
                # Dobbelt-connect på et allerede tilsluttet gphoto2-kamera fejler stille.
                try:
                    self._driver.disconnect()
                except Exception:
                    pass
                self._relay.camera.power_off()
                self._lab_relay_on = False          # tvinger re-init på næste tick
                self._do_capture_cycle()
                self._api.clear_lab_command(self._device_id)
                # _lab_relay_on er allerede False — næste _lab_tick re-initialiserer
                # relay + connect + camera-ready signal automatisk

            elif cmd_type == "get_params":
                log.info("LAB — fetching all camera params")
                try:
                    params = self._driver.get_all_config()
                    self._api._post("/lab/" + self._device_id + "/params", {"params": params})
                    log.info("LAB — sent %d params to headend", len(params))
                except Exception as exc:
                    log.warning("LAB — get_params failed: %s", exc)
                self._api.clear_lab_command(self._device_id)

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
                self._api.clear_lab_command(self._device_id)

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
                self._api.clear_lab_command(self._device_id)

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
                self._api.clear_lab_command(self._device_id)

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
                self._api.clear_lab_command(self._device_id)

        time.sleep(poll_s)

    def _lab_capture_preview(self) -> None:
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

            # Upload to headend via SFTP to _lab directory
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
                finally:
                    if sftp:
                        try: sftp.close()
                        except Exception: pass
                    if ssh:
                        try: ssh.close()
                        except Exception: pass
        except Exception as exc:
            log.warning("LAB — preview failed: %s", exc)

    # ── Shutdown ────────────────────────────────────────────────────────────

    def _shutdown(self) -> None:
        log.info("Shutting down edge agent…")
        # Ensure lab relay is OFF if we were in lab mode
        if getattr(self, "_lab_relay_on", False):
            log.info("Shutdown: forcing lab relay OFF")
            try:
                self._driver.disconnect()
            except Exception:
                pass
            try:
                self._relay.camera.force_off()
            except Exception:
                pass
            self._lab_relay_on = False
        try:
            self._relay.cleanup()
        except Exception:
            pass
        self._send_heartbeat()
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
