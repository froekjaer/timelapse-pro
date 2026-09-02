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

# Hardware identity/firmware — essentially static per physical camera (serial,
# manufacturer, model never change; firmware only after a manual update), so
# these are kept separate from CAMERA_STATUS_PARAMS above rather than growing
# it, even though they're read on the same cadence for simplicity. Each key
# lists candidate gphoto2 config paths tried in order — vendor PTP extensions
# differ: eosserialnumber/firmwareversion are Canon EOS-specific, while
# serialnumber/deviceversion are the generic PTP DeviceInfo fields Nikon (and
# most non-EOS PTP cameras) expose instead. Unverified against real Nikon Z30
# hardware in CI (needs an attached camera); see HANDOVER_LOG 2026-09-01.
CAMERA_HARDWARE_PARAMS = {
    "manufacturer":     ["/main/status/manufacturer"],
    "model":            ["/main/status/cameramodel"],
    "serial_number":    ["/main/status/eosserialnumber", "/main/status/serialnumber"],
    "firmware_version": ["/main/status/firmwareversion", "/main/status/deviceversion"],
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

# ── Key canonicalisation ────────────────────────────────────────────────────
# `expected_overrides` (built by edge/agent.py::_build_camera_commands from
# camera.* config) is NOT guaranteed to use the canonical CAMERA_CONFIG_PARAMS
# key names. Depending on the active gphoto2 camera profile
# (edge/camera/drivers/gphoto2_driver.py CAMERA_PROFILES), the same logical
# setting can arrive here as:
#   - a canonical key already ("white_balance")
#   - a short legacy gphoto2 key ("whitebalance", no underscore)
#   - a full gphoto2 config path ("/main/imgsettings/whitebalance") — this is
#     what profile-specific drivers like the Nikon Z30 profile emit, since
#     build_config_command() there returns "<path>=<value>" directly.
# Without canonicalising these, drift comparisons silently no-op (actual_val
# lookup by the wrong key returns None) — found 2026-07-05 while scoping R14
# (Nikon Z30 config drift): drift detection was effectively inert for any
# profile-driven camera because none of its override keys ever matched
# CAMERA_CONFIG_PARAMS. See HANDOVER_LOG.md 2026-07-05 for detail.
PATH_TO_CANONICAL_KEY = {path: key for key, path in CAMERA_CONFIG_PARAMS.items()}

# Legacy/short gphoto2 key name -> canonical CAMERA_CONFIG_PARAMS key.
# `None` means "no drift-check target exists for this setting" (e.g. it's a
# capture setting, not a fleet-policy parameter) — intentionally dropped, not
# a bug.
SHORT_KEY_ALIASES = {
    "iso":                   "iso",
    "whitebalance":          "white_balance",
    "picturestyle":          "picture_style",
    "colorspace":            "color_space",
    "imageformat":           "image_format",
    "meteringmode":          "metering_mode",
    "exposurecompensation":  "exposure_comp",
    "focusmode":             "focus_mode",
    "shutterspeed":          None,
    "shutter_speed":         None,
    "aperture":              None,
}


def _canonicalize_config_key(raw_key: str) -> Optional[str]:
    """Map an override/non-enforceable key (canonical, short gphoto2 name, or
    full gphoto2 path) to its canonical CAMERA_CONFIG_PARAMS key, or None if
    there is no known drift-check target for it."""
    key = (raw_key or "").strip()
    if not key:
        return None
    if key in CAMERA_CONFIG_PARAMS:
        return key
    if key in PATH_TO_CANONICAL_KEY:
        return PATH_TO_CANONICAL_KEY[key]
    short = key.split("/")[-1].lower()
    return SHORT_KEY_ALIASES.get(short)

# Shutter life ratings per camera model (conservative estimate)
# Source: Manufacturer specifications + industry standards
SHUTTER_RATINGS = {
    # Canon EOS entry-level series (100k rating is standard)
    "Canon EOS 1000D": 100_000,
    "Canon EOS 1100D": 100_000,
    "Canon EOS 1200D": 100_000,
    "Canon EOS 1300D": 100_000,
    "Canon EOS 2000D": 100_000,
    "Canon EOS 2000D/4000D": 100_000,
    "Canon EOS 4000D": 100_000,
    # Canon EOS mid-range (higher rating)
    "Canon EOS 250D": 100_000,
    "Canon EOS 90D": 150_000,
    "Canon EOS 5D Mark IV": 150_000,
    # Nikon mirrorless (Z30)
    "Nikon Z30": 100_000,
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


def _read_first_available(paths: list[str]) -> Optional[str]:
    """Try each gphoto2 config path in order, return the first non-empty
    value. Different camera vendors expose the same logical field (serial
    number, firmware version) under different PTP config paths — see
    CAMERA_HARDWARE_PARAMS."""
    for path in paths:
        val = _read_gphoto2_param(path)
        if val:
            return val
    return None


def read_camera_hardware() -> dict:
    """Read hardware identity (manufacturer/model/serial) and firmware
    version straight from the attached camera via gphoto2. Returns only the
    keys that were actually readable — a field missing here (rather than
    present-but-empty) means every candidate path failed on this body/
    firmware, not that the camera lacks the property."""
    hardware: dict[str, str] = {}
    for key, paths in CAMERA_HARDWARE_PARAMS.items():
        val = _read_first_available(paths)
        if val:
            hardware[key] = val
    return hardware


def _normalise_config_value(key: str, value: object) -> str:
    text = str(value).strip().lower()
    return VALUE_ALIASES.get(key, {}).get(text, text)


def collect_camera_diagnostics(
    camera_model: Optional[str] = None,
    expected_overrides: Optional[dict] = None,
    non_enforceable_keys: Optional[set] = None,
    include_fleet_defaults: bool = True,
) -> dict:
    """
    Read camera status and config via gphoto2.

    `expected_overrides` keys may be canonical CAMERA_CONFIG_PARAMS keys,
    short legacy gphoto2 key names, or full gphoto2 config paths — see
    `_canonicalize_config_key`. When `include_fleet_defaults` is true they are
    merged onto FLEET_DEFAULTS (an override wins per-key). Profiled cameras set
    it false and are checked only against their effective enforceable values — previously a
    non-None `expected_overrides` fully replaced FLEET_DEFAULTS, which meant
    an empty/partially-mapped overrides dict silently disabled most drift
    checks.

    `non_enforceable_keys` lists settings the active camera profile cannot or
    should not enforce (e.g. Nikon Z30 focus mode, which gphoto2 exposes as
    readonly on that body — see gphoto2_driver.CAMERA_PROFILES["Nikon Z30"]
    config_commands["focusmode"]["skip"]). These are excluded from drift
    comparison entirely rather than being flagged as expected-vs-actual
    mismatches, and are reported back under camera_config_non_enforceable
    for observability (R14: "skeln readonly vs enforceable").

    Returns a dict with:
      - camera_status: battery, shutter, available shots, lens
      - camera_config: current config values
      - camera_config_drift: list of parameters that differ from expected
      - camera_config_non_enforceable: params intentionally excluded above
      - shutter_pct: percentage of rated shutter life used
      - shutter_alarm: True if > 80% of rated life used
      - camera_hardware: manufacturer/model/serial_number/firmware_version,
        for CMDB — see CAMERA_HARDWARE_PARAMS
    """
    result = {
        "camera_status": {},
        "camera_config": {},
        "camera_config_drift": [],
        "camera_config_non_enforceable": [],
        "shutter_pct": None,
        "shutter_alarm": False,
        "camera_hardware": read_camera_hardware(),
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

    # Check for config drift against expected values. Start from fleet defaults
    # and layer any device-specific overrides on top (per-key), canonicalising
    # override keys first since they may arrive as short gphoto2 names or full
    # gphoto2 paths depending on the active camera profile.
    expected = dict(FLEET_DEFAULTS) if include_fleet_defaults else {}
    if expected_overrides:
        dropped = []
        for raw_key, value in expected_overrides.items():
            canon_key = _canonicalize_config_key(raw_key)
            if canon_key is None:
                dropped.append(raw_key)
                continue
            expected[canon_key] = value
        if dropped:
            log.debug(
                "Camera diagnostics: %d override key(s) have no drift-check "
                "mapping, skipped (not a bug — likely a capture setting, not "
                "fleet policy): %s", len(dropped), dropped
            )

    # Remove settings the active profile marks non-enforceable (e.g. readonly
    # on this body) — never compare, but do report them for observability.
    non_enforceable_canon = set()
    for raw_key in (non_enforceable_keys or []):
        canon_key = _canonicalize_config_key(raw_key)
        if canon_key:
            non_enforceable_canon.add(canon_key)
    for key in non_enforceable_canon:
        expected.pop(key, None)
    result["camera_config_non_enforceable"] = sorted(non_enforceable_canon)

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
