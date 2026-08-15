"""Concrete Service Operations backend for local technician work."""

from __future__ import annotations

import json
import os
import platform as platform_module
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

from service_platform import ServicePlatform


EDGE_ROOT = Path(os.getenv("TIMELAPSE_EDGE_ROOT", Path(__file__).resolve().parent))
EDGE_DIR = Path(os.getenv("TIMELAPSE_EDGE_DIR", "/opt/timelapse/edge"))
SERVICE_NAME = os.getenv("TIMELAPSE_EDGE_SERVICE", "timelapse-edge")

CAMERA_CONFIG_PATHS = {
    "battery": "/main/status/batterylevel",
    "model": "/main/status/cameramodel",
    "serial": "/main/status/eosserialnumber",
    "firmware": "/main/status/firmwareversion",
    "lens": "/main/status/lensname",
    "shutter_count": "/main/status/shuttercounter",
    "available_shots": "/main/status/availableshots",
    "focus_mode": "/main/capturesettings/focusmode",
    "exposure_comp": "/main/capturesettings/exposurecompensation",
    "shutter_speed": "/main/capturesettings/shutterspeed",
    "aperture": "/main/capturesettings/f-number",
    "iso": "/main/imgsettings/iso",
    "white_balance": "/main/imgsettings/whitebalance",
    "image_format": "/main/imgsettings/imageformat",
}


def create_service_platform(
    *,
    base_dir: Path | None = None,
    state_dir: Path | None = None,
    live_manager: Any | None = None,
) -> ServicePlatform:
    backend = ServiceOperations(base_dir=base_dir, live_manager=live_manager)
    platform = ServicePlatform(state_dir=state_dir)
    backend.register(platform)
    return platform


class ServiceOperations:
    def __init__(self, *, base_dir: Path | None = None, live_manager: Any | None = None):
        self.base_dir = Path(base_dir or EDGE_DIR)
        self.live_manager = live_manager
        self._restore_service_after_camera = False

    def register(self, platform: ServicePlatform) -> None:
        handlers = {
            "camera.status": self.camera_status,
            "camera.detect": self.camera_detect,
            "camera.ptp.diagnostics": self.camera_ptp_diagnostics,
            "camera.power.acquire": self.camera_power_acquire,
            "camera.power.release": self.camera_power_release,
            "camera.power.cycle": self.camera_power_cycle,
            "camera.capture.test": self.camera_capture_test,
            "camera.live.start": self.camera_live_start,
            "camera.live.stop": self.camera_live_stop,
            "camera.config.read": self.camera_config_read,
            "camera.config.diff": self.camera_config_diff,
            "camera.config.set_temporary": self.camera_config_set_temporary,
            "camera.usb.rediscover": self.camera_usb_rediscover,
            "camera.driver.reconnect": self.camera_driver_reconnect,
            "camera.hardware.inventory": self.camera_hardware_inventory,
            "camera.focus.manual": self.camera_focus_manual,
            "camera.focus.auto": self.camera_focus_auto,
            "camera.exposure.test": self.camera_exposure_test,
            "image.quality.diagnostics": self.image_quality_diagnostics,
            "camera.reset": self.camera_reset,
            "camera.diagnostics": self.camera_diagnostics,
            "modem.status": self.modem_status,
            "modem.signal": self.modem_signal,
            "modem.registration": self.modem_registration,
            "modem.reconnect_history": self.modem_reconnect_history,
            "modem.power.cycle": self.modem_power_cycle,
            "network.status": self.network_status,
            "network.diagnostics": self.network_diagnostics,
            "storage.status": self.storage_status,
            "system.status": self.system_status,
            "system.logs": self.system_logs,
            "timelapse.service.status": self.timelapse_service_status,
            "timelapse.service.restart": self.timelapse_service_restart,
            "certificate.trust.status": self.certificate_trust_status,
            "software.update.status": self.software_update_status,
            "diagnostic.bundle": self.diagnostic_bundle,
            "system.reboot": self.system_reboot,
            "commissioning.run": self.commissioning_run,
            "commissioning.validate": self.commissioning_validate,
        }
        for name, handler in handlers.items():
            if name in platform.operations:
                platform.register_handler(name, handler)
        platform.register_acquire_handler("CameraPowerLease", self.acquire_camera_power)
        platform.register_acquire_handler("ModemMaintenanceLease", self.acquire_modem)
        platform.register_cleanup_handler("LiveViewLease", self.cleanup_live_view)
        platform.register_cleanup_handler("CameraPowerLease", self.cleanup_camera_power)
        platform.register_cleanup_handler("ModemMaintenanceLease", self.cleanup_modem)

    def camera_status(self, platform: ServicePlatform, session, kwargs: dict[str, Any]) -> dict[str, Any]:
        detect = self._gphoto(["--auto-detect"], timeout=15)
        config = self._read_camera_values(("battery", "model", "serial", "lens", "focus_mode", "iso", "white_balance"))
        return {
            "ok": detect["ok"],
            "detected": "usb:" in detect["stdout"].lower(),
            "auto_detect": detect["stdout"],
            "config": config,
            "service_status": platform.status(),
        }

    def camera_detect(self, _platform, _session, _kwargs):
        result = self._gphoto(["--auto-detect"], timeout=15)
        return {"ok": result["ok"] and "usb:" in result["stdout"].lower(), **result}

    def camera_ptp_diagnostics(self, _platform, _session, _kwargs):
        detect = self._gphoto(["--auto-detect"], timeout=15)
        summary = self._gphoto(["--summary"], timeout=20)
        return {"ok": detect["ok"], "detect": detect, "summary": summary}

    def camera_power_acquire(self, _platform, _session, _kwargs):
        return {"ok": True, "camera_relay_on": True}

    def camera_power_release(self, _platform, _session, _kwargs):
        self.cleanup_camera_power(_platform, _session, "manual")
        return {"ok": True, "camera_relay_on": False}

    def camera_power_cycle(self, platform: ServicePlatform, session, kwargs: dict[str, Any]):
        self.cleanup_camera_power(platform, session, "cycle")
        time.sleep(float(kwargs.get("off_seconds", 3)))
        return self.camera_power_acquire(platform, session, kwargs)

    def camera_live_start(self, _platform, _session, kwargs: dict[str, Any]):
        if self.live_manager is None:
            return {"ok": False, "error": "live manager unavailable"}
        status = self.live_manager.start(
            max_duration_s=int(kwargs.get("max_duration_s", 180)),
            preview_interval_s=float(kwargs.get("preview_interval_s", 0.8)),
        )
        return {"ok": status.get("status") != "error", "status": status}

    def camera_live_stop(self, _platform, _session, kwargs: dict[str, Any]):
        if self.live_manager is None:
            return {"ok": True, "status": "not_running"}
        status = self.live_manager.stop(
            join_timeout_s=float(kwargs.get("join_timeout_s", 45)),
            reason=str(kwargs.get("reason", "manual")),
        )
        return {"ok": status.get("status") != "error", "status": status}

    def camera_capture_test(self, _platform, _session, kwargs: dict[str, Any]):
        out_dir = Path(kwargs.get("out_dir") or "/tmp/timelapse-tech-captures")
        out_dir.mkdir(parents=True, exist_ok=True)
        cfg = self._config()
        sys.path.insert(0, str(EDGE_ROOT))
        from camera.registry import get_driver

        driver = get_driver(cfg or self._fallback_config())
        image = None
        try:
            driver.connect()
            if not hasattr(driver, "capture_preview"):
                raise RuntimeError("camera driver does not support preview capture")
            image = driver.capture_preview(out_dir)
        finally:
            try:
                driver.disconnect()
            except Exception:
                pass
        qa = self._qa_image(image) if image else {"ok": False}
        return {"ok": True, "image": str(image), "quality": qa}

    def camera_config_read(self, _platform, _session, kwargs: dict[str, Any]):
        path = kwargs.get("path")
        if path:
            return {"ok": True, "path": path, "value": self._read_gphoto_current(str(path))}
        return {"ok": True, "config": self._read_camera_values(CAMERA_CONFIG_PATHS.keys())}

    def camera_config_set_temporary(self, platform: ServicePlatform, _session, kwargs: dict[str, Any]):
        path = str(kwargs.get("path") or "")
        value = str(kwargs.get("value") or "")
        if not path or not value:
            raise ValueError("path and value are required")
        before = self._read_gphoto_current(path)
        result = self._gphoto(["--set-config", f"{path}={value}"], timeout=15)
        after = self._read_gphoto_current(path)
        platform.record_temporary_config_change({"path": path, "before": before, "after": after, "requested": value})
        return {"ok": result["ok"], "path": path, "before": before, "after": after, "stderr": result["stderr"]}

    def camera_config_diff(self, platform: ServicePlatform, _session, _kwargs):
        return {"ok": True, "dirty": platform.status().get("config_dirty", [])}

    def camera_usb_rediscover(self, _platform, _session, _kwargs):
        return {"ok": True, "usb": self._run(["lsusb"], timeout=10)}

    def camera_driver_reconnect(self, _platform, _session, _kwargs):
        cfg = self._config()
        sys.path.insert(0, str(EDGE_ROOT))
        from camera.registry import get_driver

        driver = get_driver(cfg or self._fallback_config())
        try:
            driver.disconnect()
        except Exception:
            pass
        driver.connect()
        try:
            status = driver.status().__dict__ if hasattr(driver.status(), "__dict__") else str(driver.status())
        finally:
            try:
                driver.disconnect()
            except Exception:
                pass
        return {"ok": True, "status": status}

    def camera_hardware_inventory(self, _platform, _session, _kwargs):
        values = self._read_camera_values(("model", "serial", "firmware", "battery", "shutter_count", "available_shots", "lens"))
        detect = self._gphoto(["--auto-detect"], timeout=15)
        return {"ok": detect["ok"], "auto_detect": detect["stdout"], "inventory": values}

    def camera_focus_auto(self, _platform, _session, _kwargs):
        return self._first_gphoto_action(("/main/actions/autofocusdrive", "/main/actions/autofocus"), "1")

    def camera_focus_manual(self, _platform, _session, kwargs: dict[str, Any]):
        value = str(kwargs.get("value") or "Near 1")
        return self._first_gphoto_action(("/main/actions/manualfocusdrive", "/main/actions/manualfocusdrive2"), value)

    def camera_exposure_test(self, _platform, _session, _kwargs):
        return {"ok": True, "exposure": self._read_camera_values(("exposure_comp", "shutter_speed", "aperture", "iso"))}

    def image_quality_diagnostics(self, _platform, _session, kwargs: dict[str, Any]):
        image = kwargs.get("image")
        if not image:
            return {"ok": False, "error": "image path required"}
        return self._qa_image(Path(str(image)))

    def camera_reset(self, platform: ServicePlatform, session, kwargs: dict[str, Any]):
        return self.camera_power_cycle(platform, session, kwargs)

    def camera_diagnostics(self, platform: ServicePlatform, session, kwargs: dict[str, Any]):
        return {
            "ok": True,
            "status": self.camera_status(platform, session, kwargs),
            "ptp": self.camera_ptp_diagnostics(platform, session, kwargs),
            "inventory": self.camera_hardware_inventory(platform, session, kwargs),
            "config_diff": self.camera_config_diff(platform, session, kwargs),
        }

    def modem_status(self, _platform, _session, _kwargs):
        mmcli = self._run(["mmcli", "-L"], timeout=10) if self._command_exists("mmcli") else {"ok": False, "stderr": "mmcli missing"}
        nmcli = self._run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], timeout=10) if self._command_exists("nmcli") else {"ok": False, "stderr": "nmcli missing"}
        return {"ok": mmcli.get("ok") or nmcli.get("ok"), "mmcli": mmcli, "nmcli": nmcli}

    def modem_signal(self, _platform, _session, _kwargs):
        return {"ok": True, "signal": self._run(["mmcli", "-m", "any", "--signal-get"], timeout=10) if self._command_exists("mmcli") else None}

    def modem_registration(self, _platform, _session, _kwargs):
        return {"ok": True, "registration": self._run(["mmcli", "-m", "any"], timeout=10) if self._command_exists("mmcli") else None}

    def modem_reconnect_history(self, _platform, _session, _kwargs):
        return {"ok": True, "history": self._journal("ModemManager", lines=120)}

    def modem_power_cycle(self, _platform, _session, _kwargs):
        relay = self._relay()
        if relay is None or not hasattr(relay, "modem"):
            return {"ok": False, "warning": "modem relay unavailable"}
        relay.modem.power_cycle(reason="service operation")
        return {"ok": True}

    def network_status(self, _platform, _session, _kwargs):
        return {
            "ok": True,
            "route": self._run(["ip", "route"], timeout=10) if self._command_exists("ip") else None,
            "devices": self._run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], timeout=10) if self._command_exists("nmcli") else None,
            "dns": self._run(["resolvectl", "status"], timeout=10) if self._command_exists("resolvectl") else None,
        }

    def network_diagnostics(self, platform: ServicePlatform, session, kwargs: dict[str, Any]):
        return self.network_status(platform, session, kwargs)

    def storage_status(self, _platform, _session, _kwargs):
        cfg = self._config()
        data_path = Path(cfg.get("storage", {}).get("local_path", "/data"))
        return {"ok": True, "usage": self._disk_usage(data_path), "backlog": self._upload_backlog(cfg)}

    def system_status(self, _platform, _session, _kwargs):
        return {
            "ok": True,
            "platform": platform_module.platform(),
            "python": platform_module.python_version(),
            "uptime_s": self._uptime(),
            "load": os.getloadavg() if hasattr(os, "getloadavg") else None,
            "temperature_c": self._temperature(),
        }

    def system_logs(self, _platform, _session, kwargs: dict[str, Any]):
        return {"ok": True, "logs": self._journal(str(kwargs.get("service") or SERVICE_NAME), int(kwargs.get("lines") or 160))}

    def timelapse_service_status(self, _platform, _session, _kwargs):
        return {"ok": True, "service": self._service_state(SERVICE_NAME)}

    def timelapse_service_restart(self, _platform, _session, _kwargs):
        if not self._command_exists("systemctl"):
            return {"ok": False, "error": "systemctl missing"}
        restart = self._systemctl("restart", SERVICE_NAME, timeout=60)
        return {"ok": restart["ok"], "restart": restart, "service": self._service_state(SERVICE_NAME)}

    def certificate_trust_status(self, _platform, _session, _kwargs):
        paths = [
            Path("/etc/timelapse/edge/tls.crt"),
            Path("/etc/timelapse/edge/client.crt"),
            self.base_dir / "ssh" / "known_hosts",
        ]
        return {"ok": True, "artifacts": {str(path): {"exists": path.exists(), "size": path.stat().st_size if path.exists() else 0} for path in paths}}

    def software_update_status(self, _platform, _session, _kwargs):
        receipt = self._read_json(self.base_dir / ".timelapse-release.json")
        return {"ok": True, "release": receipt, "git_commit": os.getenv("TIMELAPSE_GIT_COMMIT", "")}

    def diagnostic_bundle(self, platform: ServicePlatform, session, kwargs: dict[str, Any]):
        out_dir = Path(kwargs.get("out_dir") or tempfile.gettempdir())
        out_dir.mkdir(parents=True, exist_ok=True)
        bundle = out_dir / f"timelapse-diagnostics-{int(time.time())}.tar.gz"
        snapshot = {
            "generated_at": _now(),
            "service": platform.status(),
            "system": self.system_status(platform, session, kwargs),
            "network": self.network_status(platform, session, kwargs),
            "storage": self.storage_status(platform, session, kwargs),
            "trust": self.certificate_trust_status(platform, session, kwargs),
            "software": self.software_update_status(platform, session, kwargs),
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snapshot.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
            with tarfile.open(bundle, "w:gz") as tar:
                tar.add(root / "snapshot.json", arcname="snapshot.json")
        return {"ok": True, "bundle": str(bundle), "snapshot": snapshot}

    def system_reboot(self, _platform, _session, kwargs: dict[str, Any]):
        if not kwargs.get("confirm"):
            return {"ok": False, "error": "confirm=true required"}
        return {"ok": self._systemctl("reboot", "", timeout=5)["ok"]}

    def commissioning_run(self, platform: ServicePlatform, session, kwargs: dict[str, Any]):
        sections = {
            "identity": self._identity_section(),
            "hardware": self.system_status(platform, session, kwargs),
            "camera": self.camera_diagnostics(platform, session, kwargs),
            "test_capture": self.camera_capture_test(platform, session, kwargs) if kwargs.get("capture") else {"ok": True, "skipped": True},
            "image_quality": {"ok": True, "source": "test_capture"} if not kwargs.get("image") else self.image_quality_diagnostics(platform, session, kwargs),
            "modem_network": {"modem": self.modem_status(platform, session, kwargs), "network": self.network_status(platform, session, kwargs)},
            "gps_time": self._gps_time_section(),
            "storage": self.storage_status(platform, session, kwargs),
            "certificates": self.certificate_trust_status(platform, session, kwargs),
            "headend": self._headend_section(),
            "software": self.software_update_status(platform, session, kwargs),
            "technician": platform.status(),
        }
        deviations = self._deviations(sections)
        if any(item["severity"] == "fail" for item in deviations):
            result = "FAIL"
        elif deviations:
            result = "PASS WITH DEVIATIONS"
        else:
            result = "PASS"
        return {
            "schema": "timelapse.edge.commissioning_report.v1",
            "generated_at": _now(),
            "result": result,
            "sections": sections,
            "deviations": deviations,
        }

    def commissioning_validate(self, platform: ServicePlatform, session, kwargs: dict[str, Any]):
        return self.commissioning_run(platform, session, {**kwargs, "capture": False})

    def cleanup_live_view(self, platform: ServicePlatform, session, reason: str) -> None:
        self.camera_live_stop(platform, session, {"reason": reason})

    def acquire_camera_power(self, _platform, _session, _reason: str) -> None:
        state = self._service_state(SERVICE_NAME)
        was_active = state.get("active") == "active" or state.get("ActiveState") == "active"
        self._restore_service_after_camera = was_active or self._service_is_enabled(SERVICE_NAME)
        if was_active:
            self._systemctl("stop", SERVICE_NAME, timeout=120)
        relay = self._relay()
        if relay is not None:
            relay.camera.power_on()

    def cleanup_camera_power(self, _platform, _session, _reason: str) -> None:
        relay = self._relay()
        if relay is not None:
            try:
                relay.camera.force_off()
            finally:
                relay.cleanup(camera=True, modem=False)
        if self._restore_service_after_camera:
            self._systemctl("start", SERVICE_NAME, timeout=60)
            self._restore_service_after_camera = False

    def acquire_modem(self, _platform, _session, _reason: str) -> None:
        return None

    def cleanup_modem(self, _platform, _session, _reason: str) -> None:
        relay = self._relay()
        if relay is not None:
            relay.cleanup(camera=False, modem=True)

    def _config(self) -> dict[str, Any]:
        for path in (self.base_dir / "config.yaml", EDGE_DIR / "config.yaml"):
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8")
                    return (yaml.safe_load(text) if yaml else json.loads(text)) or {}
                except Exception:
                    return {}
        return {}

    def _fallback_config(self) -> dict[str, Any]:
        return {"device": {"device_id": "TL-UNKNOWN"}, "camera": {}, "schedule": {}, "location": {}}

    def _relay(self):
        try:
            sys.path.insert(0, str(EDGE_ROOT))
            from camera.relay import RelayController

            return RelayController(self._config() or {})
        except Exception:
            return None

    def _gphoto(self, args: list[str], timeout: int = 15) -> dict[str, Any]:
        return self._run(["gphoto2", *args], timeout=timeout) if self._command_exists("gphoto2") else {"ok": False, "stdout": "", "stderr": "gphoto2 missing", "returncode": 127}

    def _read_gphoto_current(self, path: str) -> str | None:
        result = self._gphoto(["--get-config", path], timeout=8)
        if not result["ok"]:
            return None
        for line in result["stdout"].splitlines():
            if line.startswith("Current:"):
                return line.split(":", 1)[1].strip()
        return ""

    def _read_camera_values(self, keys) -> dict[str, Any]:
        values = {}
        for key in keys:
            path = CAMERA_CONFIG_PATHS.get(str(key), str(key))
            values[str(key)] = self._read_gphoto_current(path)
        return values

    def _first_gphoto_action(self, paths: tuple[str, ...], value: str) -> dict[str, Any]:
        for path in paths:
            probe = self._gphoto(["--get-config", path], timeout=8)
            if not probe["ok"]:
                continue
            result = self._gphoto(["--set-config", f"{path}={value}"], timeout=15)
            return {"ok": result["ok"], "path": path, "result": result}
        return {"ok": False, "error": "supported focus action not found"}

    def _qa_image(self, image: Path) -> dict[str, Any]:
        try:
            sys.path.insert(0, str(EDGE_ROOT))
            from capture.quality import QualityChecker

            report = QualityChecker(self._config()).qa_report(image)
            return {"ok": report.get("flag") != "error", "report": report}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _run(self, cmd: list[str], timeout: int = 15) -> dict[str, Any]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            return {"ok": result.returncode == 0, "returncode": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
        except Exception as exc:
            return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(exc)}

    def _command_exists(self, name: str) -> bool:
        return shutil.which(name) is not None

    def _systemctl(self, action: str, service: str, timeout: int = 30) -> dict[str, Any]:
        cmd = ["systemctl", action]
        if service:
            cmd.append(service)
        if os.geteuid() != 0 and self._command_exists("sudo"):
            cmd.insert(0, "sudo")
        return self._run(cmd, timeout=timeout)

    def _service_state(self, service: str) -> dict[str, Any]:
        if not self._command_exists("systemctl"):
            return {"active": "systemctl missing"}
        props = self._run(["systemctl", "show", service, "--property=ActiveState,SubState,NRestarts,ExecMainStatus"], timeout=5)
        state = {}
        for line in props.get("stdout", "").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                state[key] = value
        state["active"] = self._run(["systemctl", "is-active", service], timeout=5).get("stdout", "")
        return state

    def _service_is_enabled(self, service: str) -> bool:
        if not self._command_exists("systemctl"):
            return False
        result = self._run(["systemctl", "is-enabled", service], timeout=5)
        return result.get("stdout") in {"enabled", "enabled-runtime"}

    def _journal(self, service: str, lines: int = 160) -> dict[str, Any]:
        if not self._command_exists("journalctl"):
            return {"ok": False, "stderr": "journalctl missing"}
        cmd = ["journalctl", "--no-pager", "-n", str(lines)]
        if service:
            cmd.extend(["-u", service])
        return self._run(cmd, timeout=15)

    def _disk_usage(self, path: Path) -> dict[str, Any]:
        result = {}
        for target in (path, Path("/"), Path("/data")):
            if not target.exists():
                continue
            try:
                st = os.statvfs(str(target))
                total = st.f_blocks * st.f_frsize / 1e9
                free = st.f_bavail * st.f_frsize / 1e9
                key = "data" if target == path else target.as_posix().strip("/") or "root"
                result[key] = {"total_gb": round(total, 2), "free_gb": round(free, 2), "used_pct": round(100 * (total - free) / total, 1) if total else 0}
            except Exception:
                pass
        return result

    def _upload_backlog(self, config: dict[str, Any]) -> int | None:
        db_paths = [Path(config.get("storage", {}).get("local_path", "/data")) / "timelapse_edge.db", Path("/data/timelapse_edge.db")]
        for db_path in db_paths:
            if not db_path.exists():
                continue
            try:
                import sqlite3

                conn = sqlite3.connect(str(db_path))
                try:
                    return int(conn.execute("SELECT COUNT(*) FROM captures WHERE uploaded_primary = 0").fetchone()[0])
                finally:
                    conn.close()
            except Exception:
                continue
        return None

    def _uptime(self) -> int | None:
        try:
            return int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
        except Exception:
            return None

    def _temperature(self) -> float | None:
        for path in (Path("/sys/class/thermal/thermal_zone0/temp"), Path("/sys/class/thermal/thermal_zone1/temp")):
            try:
                value = int(path.read_text(encoding="utf-8").strip()) / 1000.0
                if 0 < value < 120:
                    return round(value, 1)
            except Exception:
                pass
        return None

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _identity_section(self) -> dict[str, Any]:
        bootstrap = self._read_yaml(self.base_dir / "bootstrap.yaml")
        cfg = self._config()
        return {
            "ok": bool(bootstrap.get("device_id") or cfg.get("device", {}).get("device_id")),
            "device_id": bootstrap.get("device_id") or cfg.get("device", {}).get("device_id"),
            "headend_url": bootstrap.get("headend_url") or cfg.get("headend_url"),
        }

    def _gps_time_section(self) -> dict[str, Any]:
        gps = self._run(["gpspipe", "-w", "-n", "5"], timeout=10) if self._command_exists("gpspipe") else None
        return {"ok": gps is None or gps.get("ok", False), "gps": gps, "time_utc": _now()}

    def _headend_section(self) -> dict[str, Any]:
        url = (self._read_yaml(self.base_dir / "bootstrap.yaml").get("headend_url") or "").rstrip("/")
        if not url:
            return {"ok": False, "error": "headend_url missing"}
        health_url = f"{url}/health"
        if url.endswith("/api"):
            health_url = f"{url[:-4]}/health"
        try:
            import requests

            response = requests.get(health_url, timeout=8)
            return {"ok": response.ok, "url": health_url, "status_code": response.status_code}
        except Exception as exc:
            return {"ok": False, "url": health_url, "error": str(exc)}

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            text = path.read_text(encoding="utf-8")
            return (yaml.safe_load(text) if yaml else json.loads(text)) or {}
        except Exception:
            return {}

    def _deviations(self, sections: dict[str, Any]) -> list[dict[str, str]]:
        deviations = []
        for name, value in sections.items():
            if isinstance(value, dict) and value.get("ok") is False:
                deviations.append({"section": name, "severity": "fail", "message": str(value.get("error") or "check failed")})
        camera = sections.get("camera", {})
        if isinstance(camera, dict) and camera.get("status", {}).get("detected") is False:
            deviations.append({"section": "camera", "severity": "fail", "message": "camera not detected"})
        storage = sections.get("storage", {})
        backlog = storage.get("backlog") if isinstance(storage, dict) else None
        if isinstance(backlog, int) and backlog > 0:
            deviations.append({"section": "storage", "severity": "deviation", "message": f"{backlog} captures pending upload"})
        return deviations


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
