"""
TimeLapse Pro — Configuration Manager
=======================================
Handles the three-layer configuration model:

  1. bootstrap.yaml    — device identity (written at provisioning, never changed)
  2. local_network.yaml — connectivity settings (can be overwritten by headend)
  3. config.yaml       — operational config (pulled from headend, cached locally)

SABSA: Manageability — central config control with local autonomous fallback.
       Availability  — agent always has a valid config even if headend unreachable.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any, Optional

import yaml

log = logging.getLogger(__name__)

BASE_DIR     = Path("/opt/timelapse/edge")
BOOTSTRAP    = BASE_DIR / "bootstrap.yaml"
NETWORK_CFG  = BASE_DIR / "local_network.yaml"
CONFIG_FILE  = BASE_DIR / "config.yaml"
TOKEN_FILE   = BASE_DIR / "api_token.txt"


class ConfigManager:
    """
    Loads and merges all configuration layers into a single dict.

    The merged config is the authoritative source of truth for all
    other agent components.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self._base = base_dir or BASE_DIR
        self._bootstrap:   dict = {}
        self._network:     dict = {}
        self._operational: dict = {}
        self._merged:      dict = {}

    def load(self) -> dict:
        """
        Load and merge all config layers.
        Returns the merged config dict.
        Raises on missing bootstrap (fatal).
        """
        self._bootstrap   = self._load_bootstrap()
        self._network     = self._load_network()
        self._operational = self._load_operational()
        self._merged      = self._merge()
        log.info(
            "Config loaded — device_id=%s location=%s",
            self._merged.get("device", {}).get("device_id"),
            self._merged.get("device", {}).get("location_name"),
        )
        return self._merged

    @property
    def device_id(self) -> str:
        return self._bootstrap.get("device_id") or self._derive_device_id()

    @property
    def headend_url(self) -> str:
        return self._bootstrap.get("headend_url", "https://timelapse.example.com/api")

    @property
    def bootstrap_token(self) -> Optional[str]:
        return self._bootstrap.get("bootstrap_token")

    @property
    def api_token(self) -> Optional[str]:
        token_path = self._base / "api_token.txt"
        if token_path.exists():
            return token_path.read_text().strip() or None
        return None

    def save_api_token(self, token: str) -> None:
        token_path = self._base / "api_token.txt"
        token_path.write_text(token.strip())
        log.info("API token saved")

    def save_config(self, config_dict: dict) -> None:
        """Write updated operational config to disk (from headend).
        SFTP credentials are NOT cached to disk — always fetched fresh from headend.
        """
        cfg_path = self._base / "config.yaml"
        safe_dict = {k: v for k, v in config_dict.items() if k != "sftp"}
        with open(cfg_path, "w") as f:
            yaml.dump(safe_dict, f, default_flow_style=False, allow_unicode=True)
        log.info("Operational config saved to %s", cfg_path)
        # Cache SFTP separately for cold-start resilience
        if "sftp" in config_dict:
            sftp_path = self._base / "sftp_cache.yaml"
            with open(sftp_path, "w") as f:
                yaml.dump({"sftp": config_dict["sftp"]}, f, default_flow_style=False, allow_unicode=True)
            log.info("SFTP config cached to %s", sftp_path)
        # Reload
        self._operational = config_dict
        self._merged      = self._merge()

    def save_network_config(self, network_dict: dict) -> None:
        """Write updated network config to disk (from headend)."""
        net_path = self._base / "local_network.yaml"
        with open(net_path, "w") as f:
            yaml.dump(network_dict, f, default_flow_style=False, allow_unicode=True)
        log.info("Network config saved to %s", net_path)
        self._network = network_dict
        self._merged  = self._merge()

    # ── Private loaders ────────────────────────────────────────────────────

    def _load_bootstrap(self) -> dict:
        path = self._base / "bootstrap.yaml"
        if not path.exists():
            raise FileNotFoundError(
                f"bootstrap.yaml not found at {path}. "
                "Has the device been provisioned?"
            )
        data = _load_yaml(path)
        # Inject device_id derived from MAC if not present
        if not data.get("device_id"):
            data["device_id"] = self._derive_device_id()
            log.warning(
                "device_id not in bootstrap.yaml — derived from MAC: %s",
                data["device_id"]
            )
        return data

    def _load_network(self) -> dict:
        path = self._base / "local_network.yaml"
        if not path.exists():
            log.info("local_network.yaml not found — using defaults")
            return {"connectivity": {"preferred_order": ["ethernet", "wifi"]}}
        return _load_yaml(path)

    def _load_operational(self) -> dict:
        path = self._base / "config.yaml"
        if not path.exists():
            log.warning("config.yaml not found — agent will attempt bootstrap from headend")
            return {}
        data = _load_yaml(path)
        # Inject cached SFTP config for cold-start resilience
        sftp_path = self._base / "sftp_cache.yaml"
        if sftp_path.exists() and "sftp" not in data:
            sftp_data = _load_yaml(sftp_path)
            if "sftp" in sftp_data:
                data["sftp"] = sftp_data["sftp"]
                log.info("SFTP config loaded from cold-start cache")
        return data

    def _merge(self) -> dict:
        """Deep merge all layers. Operational config wins on conflict."""
        merged = {}
        # Start from operational config as base
        _deep_update(merged, self._operational)
        # Inject bootstrap identity into device section
        device = merged.setdefault("device", {})
        device["device_id"] = self._bootstrap.get("device_id", self._derive_device_id())
        device.setdefault("headend_url", self._bootstrap.get("headend_url", ""))
        # Inject network into connectivity section
        merged["connectivity"] = self._network.get("connectivity", {})
        return merged

    @staticmethod
    def _derive_device_id() -> str:
        """Derive device_id from primary MAC address."""
        mac_int = uuid.getnode()
        mac_str = ":".join(f"{(mac_int >> (8 * i)) & 0xFF:02X}"
                           for i in reversed(range(6)))
        mac_clean = re.sub(":", "", mac_str)
        return f"TL-{mac_clean}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data or {}


def _deep_update(base: dict, update: dict) -> dict:
    """Recursively merge update into base (in-place). Returns base."""
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base
