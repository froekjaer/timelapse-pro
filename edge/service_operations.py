"""Concrete Service Operations backend for local technician work."""

from __future__ import annotations

import json
import os
import platform as platform_module
import base64
import hashlib
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, ed448, padding, rsa
from cryptography.x509.oid import ExtensionOID

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None

from service_platform import ServicePlatform


EDGE_ROOT = Path(os.getenv("TIMELAPSE_EDGE_ROOT", Path(__file__).resolve().parent))
EDGE_DIR = Path(os.getenv("TIMELAPSE_EDGE_DIR", "/opt/timelapse/edge"))
SERVICE_NAME = os.getenv("TIMELAPSE_EDGE_SERVICE", "timelapse-edge")
SSH_HOST_PUBLIC_KEY_PATHS = (
    Path("/etc/ssh/ssh_host_ed25519_key.pub"),
    Path("/etc/ssh/ssh_host_ecdsa_key.pub"),
    Path("/etc/ssh/ssh_host_rsa_key.pub"),
)

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
            "trust.ssh_host_identity": self.trust_ssh_host_identity,
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

    def certificate_trust_status(self, _platform, _session, kwargs: dict[str, Any]):
        cert_path = self._first_existing_path(
            kwargs.get("cert_path"),
            self.base_dir / "certs" / "mgmt.crt",
            Path("/etc/timelapse/certs/mgmt.crt"),
            Path("/etc/timelapse/edge/tls.crt"),
            Path("/etc/timelapse/edge/client.crt"),
        )
        ca_path = self._first_existing_path(
            kwargs.get("ca_path"),
            self.base_dir / "certs" / "edge-local-ca.crt",
            self.base_dir / "headend_ca.crt",
            Path("/etc/timelapse/certs/edge-local-ca.crt"),
            Path("/etc/timelapse/edge/headend_ca.crt"),
            Path("/etc/timelapse/ca/root/ca-cert.pem"),
            Path("/opt/timelapse/ca/root/ca-cert.pem"),
        )
        known_hosts = self.base_dir / "ssh" / "known_hosts"
        if cert_path is None:
            return {
                "ok": False,
                "error": "management certificate missing",
                "certificate": None,
                "trust_anchor": str(ca_path) if ca_path else None,
                "known_hosts": {"path": str(known_hosts), "exists": known_hosts.exists()},
            }
        try:
            cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
            now = datetime.now(timezone.utc)
            cert_info = self._certificate_info(cert, cert_path)
            cert_info["expired"] = cert.not_valid_after_utc <= now
            cert_info["not_yet_valid"] = cert.not_valid_before_utc > now
            chain = self._verify_certificate_chain(cert, ca_path)
            ok = not cert_info["expired"] and not cert_info["not_yet_valid"] and chain["ok"]
            error = None
            if cert_info["expired"]:
                error = "management certificate expired"
            elif cert_info["not_yet_valid"]:
                error = "management certificate not yet valid"
            elif not chain["ok"]:
                error = chain.get("error") or "management certificate trust verification failed"
            return {
                "ok": ok,
                "error": error,
                "certificate": cert_info,
                "chain": chain,
                "trust_anchor": str(ca_path) if ca_path else None,
                "known_hosts": {"path": str(known_hosts), "exists": known_hosts.exists(), "size": known_hosts.stat().st_size if known_hosts.exists() else 0},
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": f"management certificate invalid: {exc}",
                "certificate": {"path": str(cert_path)},
                "trust_anchor": str(ca_path) if ca_path else None,
                "known_hosts": {"path": str(known_hosts), "exists": known_hosts.exists()},
            }

    def trust_ssh_host_identity(self, _platform, _session, kwargs: dict[str, Any]):
        paths = kwargs.get("host_key_paths") or SSH_HOST_PUBLIC_KEY_PATHS
        device_id = self._identity_section().get("device_id") or "TL-UNKNOWN"
        observed_at = _now()
        keys = []
        deviations = []

        for raw_path in paths:
            path = Path(str(raw_path))
            try:
                self._assert_public_host_key_path(path)
                if not path.exists():
                    deviations.append({
                        "path": str(path),
                        "severity": "deviation",
                        "reason": "missing_public_host_key",
                    })
                    keys.append({"path": str(path), "status": "missing"})
                    continue
                key_info = self._read_ssh_public_host_key(path)
                keys.append({
                    "path": str(path),
                    "status": "observed",
                    "key_type": key_info["key_type"],
                    "fingerprint_sha256": key_info["fingerprint_sha256"],
                })
            except Exception as exc:
                deviations.append({
                    "path": str(path),
                    "severity": "fail",
                    "reason": "invalid_public_host_key",
                    "error": str(exc),
                })
                keys.append({"path": str(path), "status": "invalid", "error": str(exc)})

        observed = [item for item in keys if item.get("status") == "observed"]
        return {
            "ok": bool(observed) and not any(item.get("severity") == "fail" for item in deviations),
            "operation": "trust.ssh_host_identity",
            "schema": "timelapse.edge.ssh_host_identity.v1",
            "device_id": device_id,
            "hostname": socket.gethostname(),
            "observed_at": observed_at,
            "software": self.software_update_status(_platform, _session, kwargs).get("release", {}),
            "keys": keys,
            "deviations": deviations,
        }

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

    def _assert_public_host_key_path(self, path: Path) -> None:
        name = path.name
        if path.suffix != ".pub":
            raise ValueError("private SSH host key paths are not allowed")
        if not name.startswith("ssh_host_") or not name.endswith("_key.pub"):
            raise ValueError("only SSH public host key paths are allowed")

    def _read_ssh_public_host_key(self, path: Path) -> dict[str, str]:
        text = path.read_text(encoding="utf-8").strip()
        parts = text.split()
        if len(parts) < 2:
            raise ValueError("malformed OpenSSH public key")
        key_type, key_blob_b64 = parts[0], parts[1]
        if key_type not in {"ssh-ed25519", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521", "ssh-rsa"}:
            raise ValueError(f"unsupported SSH host key type: {key_type}")
        try:
            key_blob = base64.b64decode(key_blob_b64.encode("ascii"), validate=True)
        except Exception as exc:
            raise ValueError("malformed OpenSSH public key blob") from exc
        fingerprint = base64.b64encode(hashlib.sha256(key_blob).digest()).decode("ascii").rstrip("=")
        return {
            "key_type": self._ssh_key_type_label(key_type),
            "fingerprint_sha256": f"SHA256:{fingerprint}",
        }

    def _ssh_key_type_label(self, key_type: str) -> str:
        if key_type == "ssh-ed25519":
            return "ED25519"
        if key_type == "ssh-rsa":
            return "RSA"
        if key_type.startswith("ecdsa-"):
            return "ECDSA"
        return key_type

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
        self._collect_deviations(sections, "", deviations)
        camera = sections.get("camera", {})
        if isinstance(camera, dict) and camera.get("status", {}).get("detected") is False:
            deviations.append({"section": "camera", "severity": "fail", "message": "camera not detected"})
        storage = sections.get("storage", {})
        backlog = storage.get("backlog") if isinstance(storage, dict) else None
        if isinstance(backlog, int) and backlog > 0:
            deviations.append({"section": "storage", "severity": "deviation", "message": f"{backlog} captures pending upload"})
        return deviations

    def _collect_deviations(self, value: Any, path: str, deviations: list[dict[str, str]]) -> None:
        if not isinstance(value, dict):
            return
        if value.get("ok") is False:
            deviations.append({
                "section": path or "root",
                "severity": str(value.get("severity") or "fail"),
                "message": str(value.get("error") or value.get("message") or "check failed"),
            })
        for key, child in value.items():
            if key in {"before", "after"}:
                continue
            if isinstance(child, dict):
                child_path = f"{path}.{key}" if path else str(key)
                self._collect_deviations(child, child_path, deviations)

    def _first_existing_path(self, *paths: Any) -> Path | None:
        for item in paths:
            if not item:
                continue
            path = Path(str(item))
            if path.exists():
                return path
        return None

    def _certificate_info(self, cert: x509.Certificate, path: Path) -> dict[str, Any]:
        san = []
        try:
            ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
            san.extend(ext.get_values_for_type(x509.DNSName))
            san.extend(str(ip) for ip in ext.get_values_for_type(x509.IPAddress))
        except x509.ExtensionNotFound:
            pass
        return {
            "path": str(path),
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "serial_number": format(cert.serial_number, "x"),
            "san": san,
            "fingerprint_sha256": cert.fingerprint(hashes.SHA256()).hex(),
            "not_valid_before": cert.not_valid_before_utc.isoformat(),
            "not_valid_after": cert.not_valid_after_utc.isoformat(),
        }

    def _verify_certificate_chain(self, cert: x509.Certificate, ca_path: Path | None) -> dict[str, Any]:
        if ca_path is None:
            return {"ok": False, "error": "trust anchor missing"}
        try:
            ca_cert = x509.load_pem_x509_certificate(ca_path.read_bytes())
            now = datetime.now(timezone.utc)
            if ca_cert.not_valid_after_utc <= now:
                return {"ok": False, "error": "trust anchor expired", "ca": self._certificate_info(ca_cert, ca_path)}
            if ca_cert.not_valid_before_utc > now:
                return {"ok": False, "error": "trust anchor not yet valid", "ca": self._certificate_info(ca_cert, ca_path)}
            if cert.issuer != ca_cert.subject:
                return {"ok": False, "error": "issuer does not match trust anchor", "ca": self._certificate_info(ca_cert, ca_path)}
            self._verify_signature(ca_cert.public_key(), cert)
            return {"ok": True, "verified_by": str(ca_path), "ca": self._certificate_info(ca_cert, ca_path)}
        except InvalidSignature:
            return {"ok": False, "error": "certificate signature does not verify against trust anchor"}
        except Exception as exc:
            return {"ok": False, "error": f"trust anchor invalid: {exc}"}

    def _verify_signature(self, public_key: Any, cert: x509.Certificate) -> None:
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(cert.signature_hash_algorithm))
        elif isinstance(public_key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
            public_key.verify(cert.signature, cert.tbs_certificate_bytes)
        else:
            raise ValueError("unsupported trust anchor public key type")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
