"""
TimeLapse Pro — Diagnostics Collector
=======================================
Collects system metrics for the heartbeat payload and local database.
What is collected is controlled by the config file.

SABSA: Accountability — full operational telemetry per device.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class DiagnosticsCollector:
    """
    Collect system diagnostics as a dict for heartbeat and local DB.

    Config keys (from config.yaml diagnostics section):
        collect: list of metric names to include
            - cpu_temperature
            - cpu_load
            - memory_usage
            - disk_usage
            - battery_voltage
            - solar_voltage
            - connectivity_type
    """

    def __init__(self, config: dict):
        diag_cfg = config.get("diagnostics", {})
        self._enabled = set(diag_cfg.get("collect", [
            "cpu_temperature", "cpu_load", "memory_usage",
            "disk_usage", "connectivity_type",
        ]))
        self._data_path = Path(
            config.get("storage", {}).get("local_path", "/data")
        )

    def collect(self) -> dict:
        """Return a dict of current diagnostics."""
        result: dict = {}

        if "cpu_temperature" in self._enabled:
            result["cpu_temperature"] = self._cpu_temp()

        if "cpu_load" in self._enabled:
            result["cpu_load"] = self._cpu_load()

        if "memory_usage" in self._enabled:
            mem = self._memory()
            result.update(mem)

        if "disk_usage" in self._enabled:
            disk = self._disk_usage()
            result.update(disk)

        if "battery_voltage" in self._enabled:
            result["battery_voltage"] = self._battery_voltage()

        if "solar_voltage" in self._enabled:
            result["solar_voltage"] = self._solar_voltage()

        if "connectivity_type" in self._enabled:
            conn_type = self._connectivity_type()
            result["connectivity_type"] = conn_type
            if conn_type == "wifi":
                result["wifi_ssid"] = self._wifi_ssid()

        result["uptime_s"] = self._uptime()

        if "ntp_offset" in self._enabled or True:   # always collect
            result["ntp_offset_s"] = self._ntp_offset()

        if "ssd_usage" in self._enabled or True:    # always collect
            result.update(self._ssd_usage())

        if "service_restarts" in self._enabled or True:
            result["service_restarts"] = self._service_restarts()

        if "upload_queue" in self._enabled or True:
            result["upload_queue_size"] = self._upload_queue_size()

        return result

    # ── Individual collectors ─────────────────────────────────────────────

    def _cpu_temp(self) -> Optional[float]:
        """Read CPU temperature from thermal zone."""
        paths = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/thermal/thermal_zone1/temp",
        ]
        for p in paths:
            try:
                raw = Path(p).read_text().strip()
                temp = int(raw) / 1000.0
                if 0 < temp < 120:   # sanity check
                    return round(temp, 1)
            except (OSError, ValueError):
                pass
        return None

    def _cpu_load(self) -> Optional[float]:
        """Return 1-minute load average as a percentage of 1 core."""
        try:
            load1 = os.getloadavg()[0]
            return round(load1 * 100, 1)
        except (OSError, AttributeError):
            return None

    def _memory(self) -> dict:
        """Return used and total RAM in MB."""
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
            total_mb = info.get("MemTotal", 0) // 1024
            avail_mb = info.get("MemAvailable", 0) // 1024
            used_mb  = total_mb - avail_mb
            return {
                "memory_total_mb": total_mb,
                "memory_used_mb":  used_mb,
                "memory_free_mb":  avail_mb,
            }
        except Exception:
            return {}

    def _disk_usage(self) -> dict:
        """Return disk usage of /data in GB."""
        try:
            st = os.statvfs(str(self._data_path))
            total_gb = (st.f_blocks * st.f_frsize) / 1e9
            free_gb  = (st.f_bavail * st.f_frsize) / 1e9
            used_gb  = total_gb - free_gb
            return {
                "disk_total_gb": round(total_gb, 2),
                "disk_used_gb":  round(used_gb, 2),
                "disk_free_gb":  round(free_gb, 2),
                "disk_used_pct": round(100 * used_gb / total_gb, 1) if total_gb > 0 else 0,
            }
        except Exception:
            return {}

    def _battery_voltage(self) -> Optional[float]:
        """
        Read battery voltage from ADC or I2C sensor.
        Override this method for your specific hardware.

        Common implementations:
          - INA219 current sensor via I2C (pip install adafruit-circuitpython-ina219)
          - ADS1115 ADC via I2C (pip install adafruit-circuitpython-ads1x15)
          - Orange Pi GPIO ADC (model-dependent)
        """
        try:
            # Placeholder: read from a file written by a companion daemon
            # e.g. a simple script that polls the ADC and writes voltage to a file
            v_path = Path("/run/timelapse/battery_voltage")
            if v_path.exists():
                return float(v_path.read_text().strip())
        except Exception:
            pass
        return None

    def _solar_voltage(self) -> Optional[float]:
        """Read solar panel voltage — same pattern as battery_voltage."""
        try:
            v_path = Path("/run/timelapse/solar_voltage")
            if v_path.exists():
                return float(v_path.read_text().strip())
        except Exception:
            pass
        return None

    def _connectivity_type(self) -> Optional[str]:
        """
        Detect active network connection type.
        Returns: 'ethernet', 'wifi', '5g', or 'none'.
        """
        try:
            result = subprocess.run(
                ["ip", "route", "get", "8.8.8.8"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return "none"

            # Extract interface name from output:
            # "8.8.8.8 via 192.168.1.1 dev eth0 src ..."
            match = re.search(r"dev\s+(\S+)", result.stdout)
            if not match:
                return "none"

            iface = match.group(1)

            # Classify interface
            if re.match(r"eth|en|eno|ens", iface):
                return "ethernet"
            elif re.match(r"wl|wlan", iface):
                return "wifi"
            elif re.match(r"wwan|ppp|usb|lte|5g", iface):
                return "5g"
            else:
                return iface   # unknown — return as-is

        except Exception:
            return None

    def _wifi_ssid(self) -> Optional[str]:
        """Get current WiFi SSID."""
        try:
            r = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and parts[0] == "yes":
                    return parts[1]
        except Exception:
            pass
        return None

    def _uptime(self) -> Optional[int]:
        """Return system uptime in seconds."""
        try:
            with open("/proc/uptime") as f:
                return int(float(f.read().split()[0]))
        except Exception:
            return None

    def _ntp_offset(self) -> Optional[float]:
        """Return NTP offset in seconds via chronyc. Alarm threshold: 2s."""
        try:
            result = subprocess.run(
                ["chronyc", "tracking"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "System time" in line:
                    # "System time     :     0.000123456 seconds slow of NTP time"
                    match = re.search(r":\s+([\d.]+)\s+seconds\s+(slow|fast)", line)
                    if match:
                        offset = float(match.group(1))
                        if match.group(2) == "fast":
                            offset = -offset
                        return round(offset, 4)
        except Exception:
            pass
        # Fallback: try timedatectl
        try:
            result = subprocess.run(
                ["timedatectl", "show", "--property=NTPSynchronized,TimeUSec"],
                capture_output=True, text=True, timeout=5
            )
            if "NTPSynchronized=yes" in result.stdout:
                return 0.0  # synced but offset unknown
        except Exception:
            pass
        return None

    def _ssd_usage(self) -> dict:
        """Return disk usage of root SSD partition (/)."""
        try:
            st = os.statvfs("/")
            total_gb = (st.f_blocks * st.f_frsize) / 1e9
            free_gb  = (st.f_bavail * st.f_frsize) / 1e9
            used_gb  = total_gb - free_gb
            return {
                "ssd_total_gb": round(total_gb, 1),
                "ssd_used_gb":  round(used_gb, 1),
                "ssd_free_gb":  round(free_gb, 1),
                "ssd_used_pct": round(100 * used_gb / total_gb, 1) if total_gb > 0 else 0,
            }
        except Exception:
            return {}

    def _service_restarts(self) -> Optional[int]:
        """Return number of times timelapse-edge service has restarted."""
        try:
            result = subprocess.run(
                ["systemctl", "show", "timelapse-edge",
                 "--property=NRestarts"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if line.startswith("NRestarts="):
                    return int(line.split("=")[1])
        except Exception:
            pass
        return None

    def _upload_queue_size(self) -> Optional[int]:
        """Return number of captures waiting to be uploaded."""
        try:
            db_path = self._data_path / "timelapse_edge.db"
            if not db_path.exists():
                db_path = Path("/data/timelapse_edge.db")
            if db_path.exists():
                import sqlite3
                conn = sqlite3.connect(str(db_path))
                count = conn.execute(
                    "SELECT COUNT(*) FROM captures WHERE uploaded_primary = 0"
                ).fetchone()[0]
                conn.close()
                return count
        except Exception:
            pass
        return None
