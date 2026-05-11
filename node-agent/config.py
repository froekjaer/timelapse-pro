# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — Node Agent Config
# ═══════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import configparser
import platform
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NodeAgentConfig:
    # Identitet
    device_id:          str
    headend_url:        str         # https://timelapse.froekjaer.dk

    # Intervaller (sekunder)
    inventory_interval: int = 300   # 5 min
    security_interval:  int = 60    # 1 min

    # Platform (auto-detekteret)
    platform:           str = field(default_factory=lambda: (
        "macos" if platform.system() == "Darwin" else "linux"
    ))

    # Security collector config
    security_lookback:  int = 120   # Kig X sekunder tilbage ved hvert poll
    ssh_log_path:       str = ""    # Auto-detekteret hvis tom

    # Auth
    api_token:          str = ""
    nginx_access_log:   str = ""    # Til fremtidig JWT-auth

    @classmethod
    def load(cls, path: Path) -> "NodeAgentConfig":
        cp = configparser.ConfigParser()
        cp.read(path)
        s = cp["agent"]

        cfg = cls(
            device_id          = s["device_id"],
            headend_url        = s["headend_url"].rstrip("/"),
            inventory_interval = int(s.get("inventory_interval", "300")),
            security_interval  = int(s.get("security_interval",  "60")),
            security_lookback  = int(s.get("security_lookback",  "120")),
            ssh_log_path       = s.get("ssh_log_path", ""),
            api_token          = s.get("api_token", ""),
            nginx_access_log   = s.get("nginx_access_log", ""),
        )
        return cfg

    def to_dict(self) -> dict:
        return {
            "device_id":    self.device_id,
            "headend_url":  self.headend_url,
            "platform":     self.platform,
        }
