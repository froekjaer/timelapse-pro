"""
TimeLapse Pro — Camera Diagnostics Collector
=============================================
Reads camera status and configuration via gphoto2 and compares
against expected fleet defaults. Called once per capture cycle.

SABSA: Accountability — full camera telemetry per device.
       Manageability — detect config drift from fleet standard.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

log = logging.getLogger(__name__)

# Parameters to read from camera and their gphoto2 config paths
CAMERA_STATUS_PARAMS = {
    "battery_pct":      "/main/status/batterylevel",
    "shutter_count":    "/main/status/shuttercounter",
    "available_shots":  "/main/status/availableshots",
    "lens_name":        "/main/status/lensname",
    "serial_number":    "/main/status/eosserialnumber",
}

CAMERA_CONFIG_PARAMS = {
    "focus_mode":        "/main/capturesettings/focusmode",
    "image_format":      "/main/imgsettings/imageformat",
    "iso":               "/main/imgsettings/iso",
    "white_balance":     "/main/imgsettings/whitebalance",
    "color_space":       "/main/imgsettings/colorspace",
    "exposure_comp":     "/main/capturesettings/exposurecompensation",
    "ae_mode":           "/main/capturesettings/autoexposuremode",
    "picture_style":     "/main/capturesettings/picturestyle",
    "metering_mode":     "/main/capturesettings/meteringmode",
    "capture_target":    "/main/settings/capturetarget",
}

# Default expected values for fleet — overridable per device
# Note: capture_target excluded — Canon EOS resets to Internal RAM at power-on,
#       always controlled via initial_commands instead
FLEET_DEFAULTS = {
    "focus_mode":    "Manual",
    "image_format":  "Large Fine JPEG",
    "iso":           "Auto",
    "white_balance": "AWB White",
    "color_space":   "sRGB",
    "exposure_comp": "0",
    "ae_mode":       "P",
    "picture_style": "Neutral",
    "metering_mode": "Evaluative",
}

VALUE_ALIASES = {
    "white_balance": {
        "automatic": "auto",
        "awb white": "auto",
        "awb": "auto",
    },
    "iso": {
        "auto iso": "auto",
    },
    "focus_mode": {
        "mf": "manual",
        "manual focus": "manual",
    },
}

# Shutter life ratings per camera model (conservative estimate)
SHUTTER_RATINGS = {
    "Canon EOS 1300D": 100_000,
    "Canon EOS 2000D": 100_000,
    "Canon EOS 250D": 100_000,
    "Canon EOS 90D": 150_000,
    "Canon EOS 5D Mark IV": 150_000,
}
DEFAULT_SHUTTER_RATING = 100_000


def _read_gphoto2_param(param_path: str, timeout: int = 5) -> Optional[str]:
    """Read a single gphoto2 config parameter value."""
    try:
        result = subprocess.run(
            ["gphoto2", "--get-config", param_path],
            capture_output=True, text=True, timeout=timeout
        )
        for line in result.stdout.splitlines():
            if line.startswith("Current:"):
                return line.split(":", 1)[1].strip()
    except Exception as exc:
        log.debug("gphoto2 read failed for %s: %s", param_path, exc)
    return None


def _normalise_config_value(key: str, value: object) -> str:
    text = str(value).strip().lower()
    return VALUE_ALIASES.get(key, {}).get(text, text)


def collect_camera_diagnostics(
    camera_model: Optional[str] = None,
    expected_overrides: Optional[dict] = None,
) -> dict:
    """
    Read camera status and config via gphoto2.
    Returns a dict with:
      - camera_status: battery, shutter, available shots, lens
      - camera_config: current config values
      - camera_config_drift: list of parameters that differ from expected
      - shutter_pct: percentage of rated shutter life used
      - shutter_alarm: True if > 80% of rated life used
    """
    result = {
        "camera_status": {},
        "camera_config": {},
        "camera_config_drift": [],
        "shutter_pct": None,
        "shutter_alarm": False,
    }

    # Read status parameters
    for key, path in CAMERA_STATUS_PARAMS.items():
        val = _read_gphoto2_param(path)
        if val is not None:
            # Convert numeric fields
            if key in ("shutter_count", "available_shots"):
                try:
                    val = int(val)
                except ValueError:
                    pass
            elif key == "battery_pct":
                try:
                    val = int(val.replace("%", "").strip())
                except ValueError:
                    pass
            result["camera_status"][key] = val

    # Calculate shutter life percentage
    shutter = result["camera_status"].get("shutter_count")
    if shutter is not None:
        rating = SHUTTER_RATINGS.get(camera_model or "", DEFAULT_SHUTTER_RATING)
        pct = round(100 * shutter / rating, 1)
        result["shutter_pct"] = pct
        result["shutter_alarm"] = pct >= 80
        result["shutter_rating"] = rating
        if pct >= 80:
            log.warning(
                "Shutter count %d is %.1f%% of rated life (%d) — replacement recommended",
                shutter, pct, rating
            )

    # Read config parameters
    for key, path in CAMERA_CONFIG_PARAMS.items():
        val = _read_gphoto2_param(path)
        if val is not None:
            result["camera_config"][key] = val

    # Check for config drift against expected values. If the caller provides an
    # expected map, treat it as authoritative; otherwise use legacy fleet defaults.
    expected = dict(FLEET_DEFAULTS) if expected_overrides is None else dict(expected_overrides)

    drift = []
    for key, expected_val in expected.items():
        actual_val = result["camera_config"].get(key)
        if (
            actual_val is not None
            and _normalise_config_value(key, actual_val) != _normalise_config_value(key, expected_val)
        ):
            drift.append({
                "param":    key,
                "expected": expected_val,
                "actual":   actual_val,
            })
            log.warning(
                "Camera config drift: %s expected=%s actual=%s",
                key, expected_val, actual_val
            )

    result["camera_config_drift"] = drift

    return result
