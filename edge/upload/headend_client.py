"""
TimeLapse Pro — Headend API Client
=====================================
Handles all communication from the edge agent to the headend REST API.
Implements the pull-model: edge initiates all connections.

SABSA: Confidentiality  — JWT bearer token on every request
       Authenticity     — StrictHostKeyChecking + certificate verification
       Availability     — graceful degradation if headend unreachable
"""

from __future__ import annotations

import logging
import socket
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from security import edge_attestation_headers, ensure_edge_signing_key, request_signature_headers

log = logging.getLogger(__name__)

REQUEST_TIMEOUT  = 30    # seconds per request
MAX_RETRIES      = 3
BACKOFF_FACTOR   = 1.0   # 1s, 2s, 4s between retries


def _build_session(token: Optional[str]) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total         = MAX_RETRIES,
        backoff_factor= BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)

    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    session.headers["Content-Type"] = "application/json"
    session.headers["User-Agent"]   = "TimeLapsePro-EdgeAgent/1.0"
    return session


class HeadendClient:
    """
    REST API client for the TimeLapse Pro headend.
    All methods return (success: bool, data: dict | None).
    They never raise — failures are logged and returned as False.
    """

    def __init__(self, config: dict, config_manager):
        device = config.get("device", {})
        self._device_id  = device.get("device_id", "unknown")
        self._base_url   = device.get("headend_url", "").rstrip("/")
        self._cfg_mgr    = config_manager

    @property
    def _session(self) -> requests.Session:
        return _build_session(self._cfg_mgr.api_token)

    # ── Bootstrap ──────────────────────────────────────────────────────────

    def bootstrap(self) -> tuple[bool, Optional[dict]]:
        """
        Perform initial device registration with the headend.
        Sends device_id + bootstrap_token, receives JWT + config_url.
        """
        token = self._cfg_mgr.bootstrap_token
        if not token:
            log.error("No bootstrap_token in bootstrap.yaml")
            return False, None

        log.info("Bootstrapping device %s with headend…", self._device_id)
        return self._post("/bootstrap", {
            "device_id":       self._device_id,
            "bootstrap_token": token,
            "mac_address":     self._get_mac(),
        })

    # ── Config ──────────────────────────────────────────────────────────────

    def fetch_config(self) -> tuple[bool, Optional[dict]]:
        """Pull current operational config from headend."""
        log.debug("Fetching config for %s", self._device_id)
        return self._get(f"/config/{self._device_id}")

    def ensure_signing_enrolled(self, security_cfg: dict | None = None) -> tuple[bool, Optional[dict]]:
        """Enroll the Edge-local public signing key when Headend requests it."""
        policy = (security_cfg or {}).get("edge_signal_signing", {})
        if policy.get("registered") and policy.get("credential_id"):
            return True, {"status": "already_registered", "credential_id": policy.get("credential_id")}
        try:
            key_info = ensure_edge_signing_key(self._cfg_mgr.base_dir, self._device_id)
            payload = {
                "public_key": key_info["public_key"],
                "label": f"Edge signing key for {self._device_id}",
                "algorithm": "ed25519",
            }
            ok, data = self._post(f"/keys/signing/enroll/{self._device_id}", payload)
            if ok:
                log.info("Edge signing key enrolled: %s", data.get("credential_id") if data else "unknown")
            return ok, data
        except Exception as exc:
            log.warning("Edge signing key enrollment failed: %s", exc)
            return False, None

    # ── Heartbeat ───────────────────────────────────────────────────────────

    def send_heartbeat(self, diagnostics: dict, capture_stats: dict) -> tuple[bool, Optional[dict]]:
        """
        Send periodic heartbeat with diagnostics and capture statistics.
        Interval: 60 minutes (configurable in config.yaml).
        """
        payload = {
            "device_id":     self._device_id,
            "timestamp":     _now(),
            "diagnostics":   diagnostics,
            "capture_stats": capture_stats,
            "ip_address":    self._get_ip(),
        }
        log.debug("Sending heartbeat for %s", self._device_id)
        return self._post(f"/heartbeat/{self._device_id}", payload)

    # ── Capture metadata sync ───────────────────────────────────────────────

    def sync_capture(self, capture_row: dict) -> tuple[bool, Optional[dict]]:
        """
        Post capture metadata to headend for the web dashboard.
        Does not transfer the image — only metadata + quality result.
        """
        payload = {
            "device_id":       self._device_id,
            "filename":        capture_row.get("filename"),
            "sha256":          capture_row.get("sha256"),
            "captured_at":     capture_row.get("captured_at"),
            "filesize":        capture_row.get("filesize"),
            "camera_model":    capture_row.get("camera_model"),
            "quality_flag":    capture_row.get("quality_flag"),
            "quality_passed":  bool(capture_row.get("quality_passed")),
            "blur_score":      capture_row.get("blur_score"),
            "brightness_mean": capture_row.get("brightness_mean"),
            "uploaded_primary":bool(capture_row.get("uploaded_primary")),
            "exposure_time":   capture_row.get("exposure_time"),
            "aperture":        capture_row.get("aperture"),
            "iso":             capture_row.get("iso"),
        }
        return self._post(f"/captures/{self._device_id}", payload)

    # ── Reverse SSH ──────────────────────────────────────────────────────────

    def notify_tunnel_ready(self, port: int) -> tuple[bool, Optional[dict]]:
        """Notify headend that reverse SSH tunnel is ready on given port."""
        return self._post("/reverse-ssh/ready", {
            "device_id": self._device_id,
            "port":      port,
            "timestamp": _now(),
        })

    # ── Events ───────────────────────────────────────────────────────────────

    def send_event(
        self,
        level:    str,
        category: str,
        message:  str,
        extra:    Optional[dict] = None,
    ) -> tuple[bool, Optional[dict]]:
        return self._post(f"/events/{self._device_id}", {
            "device_id": self._device_id,
            "timestamp": _now(),
            "level":     level,
            "category":  category,
            "message":   message,
            "extra":     extra or {},
        })

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str) -> tuple[bool, Optional[dict]]:
        url = f"{self._base_url}{path}"
        try:
            headers = request_signature_headers(self._cfg_mgr.api_token, "GET", path)
            headers.update(edge_attestation_headers(self._cfg_mgr.base_dir, self._device_id, "GET", path))
            resp = self._session.get(url, headers=headers, timeout=REQUEST_TIMEOUT, verify=True)
            if resp.status_code == 200:
                return True, resp.json()
            log.warning("GET %s → HTTP %d", path, resp.status_code)
            return False, None
        except Exception as exc:
            log.warning("GET %s failed: %s", path, exc)
            return False, None

    def ping(self) -> bool:
        """Returnerer True hvis headend API er tilgængeligt."""
        try:
            session = _build_session(self._cfg_mgr.api_token)
            r = session.get(f"{self._base_url}/api/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def _post(self, path: str, payload: dict) -> tuple[bool, Optional[dict]]:
        url = f"{self._base_url}{path}"
        try:
            headers = request_signature_headers(self._cfg_mgr.api_token, "POST", path, payload)
            if not path.startswith("/keys/signing/enroll/"):
                headers.update(edge_attestation_headers(self._cfg_mgr.base_dir, self._device_id, "POST", path, payload))
            resp = self._session.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT, verify=True)
            if resp.status_code in (200, 201):
                return True, resp.json()
            log.warning("POST %s → HTTP %d: %s", path, resp.status_code, resp.text[:200])
            return False, None
        except requests.exceptions.ConnectionError:
            log.warning("POST %s: headend unreachable", path)
            return False, None
        except Exception as exc:
            log.warning("POST %s failed: %s", path, exc)
            return False, None

    def download_artifact_file(self, artifact_id: str, file_path: str) -> tuple[bool, bytes | None]:
        path = f"/updates/artifacts/{artifact_id}/files/{file_path}"
        url = f"{self._base_url}{path}"
        try:
            headers = request_signature_headers(self._cfg_mgr.api_token, "GET", path)
            headers.update(edge_attestation_headers(self._cfg_mgr.base_dir, self._device_id, "GET", path))
            resp = self._session.get(
                url,
                params={"device_id": self._device_id},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                verify=True,
            )
            if resp.status_code == 200:
                return True, resp.content
            log.warning("GET artifact %s:%s → HTTP %d: %s", artifact_id, file_path, resp.status_code, resp.text[:200])
            return False, None
        except Exception as exc:
            log.warning("GET artifact %s:%s failed: %s", artifact_id, file_path, exc)
            return False, None


    def clear_lab_command(self, device_id: str) -> None:
        """Clear pending lab command after execution."""
        self._post(f"/admin/devices/{device_id}/lab-clear-command", {})

    def clear_lab_params(self, device_id: str) -> None:
        """Clear pending_params after applying them."""
        self._post(f"/admin/devices/{device_id}/lab-clear-params", {})

    # ── System helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _get_ip() -> Optional[str]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception:
            return None

    @staticmethod
    def _get_mac() -> Optional[str]:
        import uuid as _uuid
        import re
        mac_int = _uuid.getnode()
        return ":".join(f"{(mac_int >> (8 * i)) & 0xFF:02X}"
                        for i in reversed(range(6)))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
