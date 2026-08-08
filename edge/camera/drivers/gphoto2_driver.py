# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — gphoto2_driver.py
# ───────────────────────────────────────────────────────────────────────────
# Version  : 2.2.0
# Dato     : 13. april 2026
# ───────────────────────────────────────────────────────────────────────────
# Changelog:
#   2.2.0  13-apr-2026  Sidecar JSON metadata — integritet bevares
#                       Original JPEG aldrig modificeret (SHA-256 uberørt)
#                       Skriver .json ved siden af hvert billede med:
#                         - sha256 af original, capture tidspunkt UTC
#                         - GPS, azimuth, tilt, FOV, montagehøjde
#                         - Kunde, site, kamera metadata
#                         - Kamera EXIF (ISO, lukker, blænde, model)
#   2.1.0  11-apr-2026  Lokal tidszone til filnavn og SFTP mappestruktur
#   2.0.0  10-apr-2026  Hierarkisk config, focusmode fix
# ═══════════════════════════════════════════════════════════════════════════
"""
TimeLapse Pro — gPhoto2 Camera Driver
======================================
Implements CameraBase for USB/PTP cameras via gphoto2 CLI.
Tested with: Canon EOS 1300D, EOS 2000D, EOS 800D, Nikon Z30.

Design decisions:
  - Uses gphoto2 CLI (not the Python binding) for maximum compatibility
    and simpler error handling / subprocess isolation.
  - Camera power is managed externally via GPIO relay — this driver
    assumes the camera is already powered on when connect() is called.
  - Images are downloaded to a temp path first, then moved to dest_dir
    atomically to avoid partial-file reads by the upload manager.
  - SHA-256 is computed immediately after download, before the temp
    file is moved, to catch any download corruption.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from camera.base import (
    CameraBase,
    CameraError,
    CameraNotFoundError,
    CameraState,
    CameraStatus,
    CameraTimeoutError,
    CaptureResult,
    CaptureFailed,
)

log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

GPHOTO2_CMD          = "gphoto2"
CONNECT_TIMEOUT_S    = 15
CAPTURE_TIMEOUT_S    = 60   # generous — RAW takes longer
DOWNLOAD_TIMEOUT_S   = 30
STATUS_TIMEOUT_S     = 10
HEALTH_TIMEOUT_S     = 5
MAX_DETECT_RETRIES   = 3
DETECT_RETRY_DELAY_S = 2


def _number_or_none(value) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_gpsd_fix(timeout_s: int = 10) -> dict:
    """Read one usable TPV fix from gpsd via gpspipe when available.

    NOTE (2026-07-03, RETTET root-cause): den oprindelige implementering brugte
    `gpspipe -w -n N` og stolede på gpspipes egen linje-tælling for at afgøre
    hvornår processen selv afslutter. Det tæller ALLE JSON-beskeder (VERSION/
    DEVICES/WATCH-kvittering + interfolierede SKY-rapporter), ikke kun TPV.
    Ved ca. 2 beskeder/sekund kræver N=40 op mod 18-19 sekunders strømtid —
    langt over enhver fornuftig subprocess-timeout, så gpspipe blev ALTID
    dræbt af vores egen timeout før den nåede at afslutte selv, uanset om
    gpsd havde et gyldigt fix. Bekræftet reproducerbart via `sudo systemd-run`
    med identisk sandboxing som selve edge-servicen (udelukker permissions/
    ProtectSystem som årsag — det var en ren regnefejl i linje-vs-tid).
    Erstattet med line-by-line-læsning bundet af et wall-clock-deadline:
    stopper med det samme der ses et brugbart TPV (mode>=2), ellers efter
    `timeout_s` sekunder uanset hvor mange beskeder der er modtaget.
    """
    import select as _select

    try:
        proc = subprocess.Popen(
            ["gpspipe", "-w"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        log.debug("gpspipe not installed; live GPS metadata skipped")
        return {}
    except Exception as exc:
        log.warning("gpsd metadata-læsning fejlede (start): %s", exc)
        return {}

    deadline = time.monotonic() + timeout_s
    tpv_seen = 0
    fix: dict = {}
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = _select.select([proc.stdout], [], [], remaining)
            if not ready:
                break
            line = proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if msg.get("class") != "TPV":
                continue
            tpv_seen += 1
            mode = int(msg.get("mode") or 0)
            lat = _number_or_none(msg.get("lat"))
            lon = _number_or_none(msg.get("lon"))
            if mode < 2 or lat is None or lon is None:
                continue
            fix = {
                "gps_lat": lat,
                "gps_lon": lon,
                "gps_source": "gpsd",
            }
            alt = _number_or_none(msg.get("altHAE") if msg.get("altHAE") is not None else msg.get("altMSL"))
            if alt is not None:
                fix["gps_alt"] = alt
            break
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    if fix:
        return fix
    log.warning(
        "Intet brugbart GPS-fix fra gpsd inden for %ss (%d TPV-beskeder modtaget, ingen med mode>=2)",
        timeout_s, tpv_seen,
    )
    return {}


# ═══════════════════════════════════════════════════════════════════════════
# Camera Profiles — TimeLapse Pro
# Version: 2.0.0 | 2026-07-07
# ────────────────────────────────────────────────────────────────────────────────
#
# Design principles:
#   1. Shared settings defined once in base profile (inherited by all)
#   2. Camera-specific features in dedicated profiles
#   3. All settings that affect image hash are explicitly listed
#   4. GPS/NTP sync capabilities documented per camera
#   5. Shutter life ratings documented per model
#
# Hash inclusion policy:
#   Any setting listed in config_commands, capture_settings, or camera_capabilities
#   will be included in the camera config hash used for drift detection.
# ═══════════════════════════════════════════════════════════════════════════

# ── Base Profile: Shared Settings ────────────────────────────────────────────
# These settings are common across all supported camera models.
# Individual camera profiles inherit and can override specific paths.
_BASE_CAMERA_PROFILE = {
    "name": "Base Camera Profile",
    "description": "Shared configuration inherited by all camera profiles",
    # Shutter life rating (actuations) — used for diagnostics/alarm
    "shutter_rating": 100_000,
    # Capture settings — paths for reading current values after capture
    "capture_settings": {
        "exposure_time": ["/main/capturesettings/shutterspeed"],
        "aperture": [
            "/main/capturesettings/aperture",
            "/main/capturesettings/f-number",
        ],
        "iso": [
            "/main/capturesettings/iso",
            "/main/imgsettings/iso",
        ],
        "focus_mode": ["/main/capturesettings/focusmode"],
    },
    # Config commands — for writing settings (drift-checked)
    # All these settings are included in camera config hash
    "config_commands": {
        "iso": {
            "path": "/main/imgsettings/iso",
            "skip_values": ["Auto", "auto", ""],
        },
        "shutter_speed": {
            "path": "/main/capturesettings/shutterspeed",
            "skip_values": ["Auto", "auto", ""],
        },
        "aperture": {
            "path": "/main/capturesettings/f-number",
            "skip_values": ["Auto", "auto", ""],
        },
        "whitebalance": {
            "path": "/main/imgsettings/whitebalance",
            "value_map": {
                "Auto": "Automatic",
                "AWB White": "Automatic",
                "Daylight": "Daylight",
                "Cloudy": "Cloudy",
                "Tungsten": "Incandescent",
                "Fluorescent": "Fluorescent",
                "Flash": "Flash",
                "Shade": "Shade",
            },
        },
        "colorspace": {"path": "/main/imgsettings/colorspace"},
        "imageformat": {"path": "/main/imgsettings/imageformat"},
        "exposurecompensation": {"path": "/main/capturesettings/exposurecompensation"},
        "picturestyle": {"path": "/main/capturesettings/picturestyle"},
        "meteringmode": {"path": "/main/capturesettings/meteringmode"},
        "autoexposuremode": {"path": "/main/capturesettings/autoexposuremode"},
    },
    # Camera capabilities — what this camera class can do
    "camera_capabilities": {
        "autofocus": False,        # Can trigger autofocus via software
        "remote_focus": False,    # Can drive focus motor via software
        "liveview": True,         # Can preview live view
        "movie": False,           # Can record video
        "gps_sync": False,        # Can sync internal clock from GPS/NTP
        "location_embed": False,  # Can embed GPS coordinates in EXIF
        "datetime_sync": True,    # Can set date/time via gphoto2
    },
    # Actions — gphoto2 action paths
    "actions": {},
    # Focus controls — for cameras with motorized focus
    "focus_controls": {},
}

# ── Camera Profiles ───────────────────────────────────────────────────────────────
CAMERA_PROFILES = {
    "default": {
        **_BASE_CAMERA_PROFILE,
        "name": "Generic gPhoto2 Camera",
        "description": "Fallback profile for unknown cameras",
    },

    # ── Canon EOS 1000D (Rebel XS) ────────────────────────────────────────────────
    "Canon EOS 1000D": {
        **_BASE_CAMERA_PROFILE,
        "name": "Canon EOS 1000D",
        "description": "Entry-level DSLR from 2008, 10.1MP",
        "shutter_rating": 100_000,
        # Override capture settings with model-specific paths
        "capture_settings": {
            "exposure_time": ["/main/capturesettings/shutterspeed"],
            "aperture": ["/main/capturesettings/f-number"],
            "iso": ["/main/imgsettings/iso"],
            "focus_mode": ["/main/capturesettings/focusmode"],
        },
        "config_commands": {
            **_BASE_CAMERA_PROFILE["config_commands"],
            # EOS 1000D specific value mappings
            "whitebalance": {
                "path": "/main/imgsettings/whitebalance",
                "value_map": {
                    "Auto": "AWB White",
                    "Daylight": "Daylight",
                    "Cloudy": "Cloudy",
                    "Tungsten": "Tungsten",
                    "Fluorescent": "Fluorescent",
                    "Flash": "Flash",
                },
            },
        },
        "camera_capabilities": {
            **_BASE_CAMERA_PROFILE["camera_capabilities"],
            "datetime_sync": True,
        },
        "actions": {
            "viewfinder": "/main/actions/viewfinder",
        },
    },

    # ── Canon EOS 1300D (Rebel T6) ────────────────────────────────────────────────
    "Canon EOS 1300D": {
        **_BASE_CAMERA_PROFILE,
        "name": "Canon EOS 1300D",
        "description": "Entry-level DSLR from 2016, 18MP with WiFi",
        "shutter_rating": 100_000,
        "capture_settings": {
            "exposure_time": ["/main/capturesettings/shutterspeed"],
            "aperture": ["/main/capturesettings/f-number"],
            "iso": [
                "/main/capturesettings/iso",
                "/main/imgsettings/iso",
            ],
            "focus_mode": ["/main/capturesettings/focusmode"],
        },
        "camera_capabilities": {
            **_BASE_CAMERA_PROFILE["camera_capabilities"],
            "datetime_sync": True,
            "wifi_transfer": True,  # Can transfer via WiFi (not used in TimeLapse Pro)
        },
        "actions": {
            "viewfinder": "/main/actions/viewfinder",
        },
    },

    # ── Canon EOS 2000D (Rebel T7) ────────────────────────────────────────────────
    "Canon EOS 2000D": {
        **_BASE_CAMERA_PROFILE,
        "name": "Canon EOS 2000D",
        "description": "Entry-level DSLR from 2018, 24.1MP",
        "shutter_rating": 100_000,
        "capture_settings": {
            "exposure_time": ["/main/capturesettings/shutterspeed"],
            "aperture": ["/main/capturesettings/f-number"],
            "iso": [
                "/main/capturesettings/iso",
                "/main/imgsettings/iso",
            ],
            "focus_mode": ["/main/capturesettings/focusmode"],
        },
        "camera_capabilities": {
            **_BASE_CAMERA_PROFILE["camera_capabilities"],
            "datetime_sync": True,
            "wifi_transfer": True,
        },
        "actions": {
            "viewfinder": "/main/actions/viewfinder",
        },
    },

    # ── Canon EOS 2000D variant (alternative model name) ─────────────────────────────
    "Canon EOS 2000D/4000D": {
        **_BASE_CAMERA_PROFILE,
        "name": "Canon EOS 2000D/4000D",
        "description": "Entry-level DSLR series, similar config",
        "shutter_rating": 100_000,
    },

    # ── Nikon Z30 ───────────────────────────────────────────────────────────────────
    "Nikon Z30": {
        **_BASE_CAMERA_PROFILE,
        "name": "Nikon Z30",
        "description": "APS-C mirrorless from 2022, 20.9MP",
        "shutter_rating": 100_000,
        "capture_settings": {
            "exposure_time": [
                "/main/capturesettings/shutterspeed",
                "/main/capturesettings/shutterspeed2",
            ],
            "aperture": ["/main/capturesettings/f-number"],
            "iso": ["/main/imgsettings/iso"],
            "focus_mode": ["/main/capturesettings/focusmode"],
        },
        "config_commands": {
            **_BASE_CAMERA_PROFILE["config_commands"],
            # Z30-specific config paths and behaviors
            "iso": {
                "path": "/main/imgsettings/iso",
                # Z30 exposes concrete ISO values; "Auto" is mode-dependent
                "skip_values": ["Auto", "auto", ""],
            },
            "shutter_speed": {
                "path": "/main/capturesettings/shutterspeed",
                "skip_values": ["Auto", "auto", ""],
            },
            "aperture": {
                "path": "/main/capturesettings/f-number",
                "skip_values": ["Auto", "auto", ""],
            },
            "whitebalance": {
                "path": "/main/imgsettings/whitebalance",
                "value_map": {
                    "Auto": "Automatic",
                    "AWB White": "Automatic",
                    "Cloudy": "Cloudy",
                    "Daylight": "Daylight",
                    "Tungsten": "Incandescent",
                    "Fluorescent": "Fluorescent",
                    "Flash": "Flash",
                },
            },
            "colorspace": {"path": "/main/imgsettings/colorspace"},
            "imageformat": {"path": "/main/capturesettings/imagequality"},
            "exposurecompensation": {"path": "/main/capturesettings/exposurecompensation"},
            # Focus mode is readonly on Z30 in current firmware
            "focusmode": {"skip": True},
        },
        "camera_capabilities": {
            **_BASE_CAMERA_PROFILE["camera_capabilities"],
            "autofocus": True,        # Can trigger autofocus drive
            "remote_focus": True,    # Can drive focus motor in steps
            "liveview": True,
            "movie": True,
            "datetime_sync": True,
        },
        "actions": {
            "autofocus": "/main/actions/autofocusdrive",
            "manual_focus": "/main/actions/manualfocusdrive",
            "viewfinder": "/main/actions/viewfinder",
            "movie": "/main/actions/movie",
            "control_mode": "/main/actions/controlmode",
        },
        "focus_controls": {
            "manual_focus_default_step": "500",
            "manual_focus_min": "-32767",
            "manual_focus_max": "32767",
            "manual_focus_context": {
                "/main/capturesettings/liveviewaffocus": "Manual Focus (selection)",
                "/main/actions/viewfinder": "1",
            },
        },
    },

    # ── Legacy: Generic Canon EOS ───────────────────────────────────────────────────
    # Fallback for any Canon EOS camera not specifically listed
    "Canon EOS": {
        **_BASE_CAMERA_PROFILE,
        "name": "Canon EOS (Generic)",
        "description": "Generic Canon EOS profile for unlisted models",
        "shutter_rating": 100_000,
        "actions": {
            "viewfinder": "/main/actions/viewfinder",
        },
    },
}

# ── Camera Metadata Table ───────────────────────────────────────────────────────────
# Quick reference for camera model information used by diagnostics and UI
CAMERA_METADATA = {
    "Canon EOS 1000D": {
        "shutter_rating": 100_000,
        "megapixels": 10.1,
        "release_year": 2008,
        "sensor": "APS-C CMOS",
        "gps_embed": False,
        "datetime_sync": True,
    },
    "Canon EOS 1300D": {
        "shutter_rating": 100_000,
        "megapixels": 18.0,
        "release_year": 2016,
        "sensor": "APS-C CMOS",
        "gps_embed": False,
        "datetime_sync": True,
        "wifi": True,
    },
    "Canon EOS 2000D": {
        "shutter_rating": 100_000,
        "megapixels": 24.1,
        "release_year": 2018,
        "sensor": "APS-C CMOS",
        "gps_embed": False,
        "datetime_sync": True,
        "wifi": True,
    },
    "Canon EOS 4000D": {
        "shutter_rating": 100_000,
        "megapixels": 18.0,
        "release_year": 2017,
        "sensor": "APS-C CMOS",
        "gps_embed": False,
        "datetime_sync": True,
    },
    "Nikon Z30": {
        "shutter_rating": 100_000,
        "megapixels": 20.9,
        "release_year": 2022,
        "sensor": "APS-C CMOS",
        "gps_embed": False,
        "datetime_sync": True,
        "autofocus_drive": True,
        "mirrorless": True,
    },
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _run(args: list[str], timeout: int, check: bool = True) -> subprocess.CompletedProcess:
    """Run gphoto2 subprocess, return CompletedProcess."""
    cmd_text = " ".join(args)
    started = time.monotonic()
    log.info("gphoto2 exec: %s", cmd_text)
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        stdout = (result.stdout or "").strip().replace("\n", " | ")
        stderr = (result.stderr or "").strip().replace("\n", " | ")
        log.info(
            "gphoto2 result: rc=%s duration_ms=%s stdout=%r stderr=%r",
            result.returncode,
            elapsed_ms,
            stdout[:300],
            stderr[:300],
        )
        if check and result.returncode != 0:
            raise CameraError(
                f"gphoto2 returned {result.returncode}: {result.stderr.strip()}"
            )
        return result
    except subprocess.TimeoutExpired as exc:
        raise CameraTimeoutError(
            f"gphoto2 timed out after {timeout}s: {' '.join(args)}"
        ) from exc
    except FileNotFoundError as exc:
        raise CameraError(
            "gphoto2 not found — run: apt install gphoto2"
        ) from exc


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_external(args: list[str], timeout: int, label: str) -> subprocess.CompletedProcess:
    cmd_text = " ".join(str(a) for a in args)
    started = time.monotonic()
    log.info("%s exec: %s", label, cmd_text)
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout = (result.stdout or "").strip().replace("\n", " | ")
    stderr = (result.stderr or "").strip().replace("\n", " | ")
    log.info(
        "%s result: rc=%s duration_ms=%s stdout=%r stderr=%r",
        label,
        result.returncode,
        elapsed_ms,
        stdout[:300],
        stderr[:300],
    )
    return result


def _read_shutter_count_from_exif(image_path: Path) -> tuple[Optional[int], Optional[str]]:
    """Read shutter count from a captured image's MakerNotes via exiftool.

    Nikon embeds this per-file (unlike Canon's live PTP counter) — prefer
    MechanicalShutterCount when present (excludes electronic-shutter-only
    frames, which don't wear the mechanical shutter), fall back to the
    combined ShutterCount. Returns (count, source) or (None, None) if
    exiftool isn't installed or this camera doesn't embed either tag.
    """
    result = _run_external(
        ["exiftool", "-j", "-ShutterCount", "-MechanicalShutterCount", str(image_path)],
        timeout=15, label="exiftool-shuttercount",
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None, None
    try:
        parsed = json.loads(result.stdout)
    except (ValueError, json.JSONDecodeError):
        return None, None
    if not parsed:
        return None, None
    tags = parsed[0]
    if tags.get("MechanicalShutterCount") is not None:
        try:
            return int(tags["MechanicalShutterCount"]), "nikon_exif_mechanical"
        except (TypeError, ValueError):
            pass
    if tags.get("ShutterCount") is not None:
        try:
            return int(tags["ShutterCount"]), "nikon_exif_total"
        except (TypeError, ValueError):
            pass
    return None, None


# ── Driver ────────────────────────────────────────────────────────────────────

def _parse_gphoto2_config(output: str) -> list[dict]:
    """Parse output of gphoto2 --list-all-config into structured dicts."""
    params = []
    current: dict = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("/main/"):
            if current.get("path"):
                params.append(current)
            current = {"path": line, "label": "", "type": "", "current": "",
                       "choices": [], "readonly": False}
        elif line.startswith("Label:"):
            current["label"] = line.split(":", 1)[1].strip()
        elif line.startswith("Type:"):
            current["type"] = line.split(":", 1)[1].strip()
        elif line.startswith("Readonly:"):
            current["readonly"] = line.split(":", 1)[1].strip() == "1"
        elif line.startswith("Current:"):
            current["current"] = line.split(":", 1)[1].strip()
        elif line.startswith("Bottom:"):
            current["bottom"] = line.split(":", 1)[1].strip()
        elif line.startswith("Top:"):
            current["top"] = line.split(":", 1)[1].strip()
        elif line.startswith("Step:"):
            current["step"] = line.split(":", 1)[1].strip()
        elif line.startswith("Choice:"):
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                current["choices"].append({"index": parts[1], "label": parts[2]})
        elif line == "END" and current.get("path"):
            params.append(current)
            current = {}
    return params


class GPhoto2Driver(CameraBase):
    """
    gPhoto2-based driver for USB/PTP cameras.

    Config keys (from config.yaml camera section):
        gphoto2_port:          str   e.g. "usb:" or "usb:001,004"
        capture_timeout:       int   seconds (default 60)
        download_timeout:      int   seconds (default 30)
        delete_after_download: bool  (default true)
    """

    SUPPORTED = [
        "Canon EOS 1300D", "Canon EOS 1200D", "Canon EOS 1100D",
        "Canon EOS 2000D", "Canon EOS 4000D", "Canon EOS 800D",
        "Canon EOS 750D", "Canon EOS 700D", "Canon EOS 650D",
        "Canon EOS 600D", "Canon EOS 550D", "Canon EOS 100D",
        "Canon EOS 200D", "Canon EOS 250D", "Canon EOS 90D",
        "Canon EOS 80D",  "Canon EOS 77D",  "Canon EOS 760D",
        "Nikon Z30",
    ]

    def __init__(self, config: dict):
        super().__init__(config)
        self._port:         str           = config.get("gphoto2_port", "usb:")
        self._model:        Optional[str] = None
        self._cap_timeout:  int           = config.get("capture_timeout", CAPTURE_TIMEOUT_S)
        self._dl_timeout:   int           = config.get("download_timeout", DOWNLOAD_TIMEOUT_S)
        self._delete_after: bool          = config.get("delete_after_download", True)
        self._profile:      dict          = CAMERA_PROFILES["default"]
        self._profile_key:  str           = "default"
        self._settings_cache: Optional[tuple[Optional[str], Optional[str], Optional[int], Optional[str]]] = None
        # 2026-07-04 (Peter): GPS-modtageren mister fix naar kamera-relaeet
        # taendes. Kameraet sidder fast monteret og flytter sig aldrig, saa
        # GPS laeses i stedet mens relaeet er slukket (agentens idle-ventetid
        # mellem optagelser, se agent.py._tick -> refresh_gps_cache()) og
        # caches her. En gammel god fix er langt bedre end intet, saa et
        # mislykket forsog overskriver ALDRIG et allerede cachet fix.
        self._last_gps_fix: dict = {}

    def refresh_gps_cache(self) -> None:
        """Forsog at opdatere det cachede GPS-fix. Kaldes af agenten mens
        kamera-relaeet er slukket. Se kommentar i __init__ for hvorfor."""
        loc = self._config.get("location", {}) or {}
        if loc.get("gps_source") != "gpsd":
            return
        fix = _read_gpsd_fix()
        if fix:
            self._last_gps_fix = fix

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Detect camera on USB, verify it responds."""
        log.info("Connecting to camera via gphoto2 (port=%s)…", self._port)

        for attempt in range(1, MAX_DETECT_RETRIES + 1):
            try:
                result = _run(
                    [GPHOTO2_CMD, "--auto-detect"],
                    timeout=CONNECT_TIMEOUT_S,
                )
                # Parse model from output:
                #   Model                          Port
                #   Canon EOS 1300D                usb:002,004
                lines = result.stdout.strip().splitlines()
                for line in lines[2:]:  # skip header rows
                    if "usb" in line.lower() or "ptpip" in line.lower():
                        self._model = line.split("  ")[0].strip()
                        break

                if not self._model:
                    raise CameraNotFoundError("No camera found by gphoto2 --auto-detect")

                self._profile_key, self._profile = self._profile_for_model(self._model)
                log.info("Camera detected: %s", self._model)
                self._connected = True
                return

            except (CameraNotFoundError, CameraError) as exc:
                if attempt < MAX_DETECT_RETRIES:
                    log.warning(
                        "Detection attempt %d/%d failed: %s — retrying in %ds",
                        attempt, MAX_DETECT_RETRIES, exc, DETECT_RETRY_DELAY_S
                    )
                    time.sleep(DETECT_RETRY_DELAY_S)
                else:
                    raise CameraNotFoundError(
                        f"Camera not found after {MAX_DETECT_RETRIES} attempts: {exc}"
                    ) from exc

    def disconnect(self) -> None:
        """Release camera. For gphoto2 CLI this is a no-op."""
        self._connected = False
        self._model = None
        self._profile = CAMERA_PROFILES["default"]
        self._profile_key = "default"
        self._settings_cache = None
        log.debug("gPhoto2Driver disconnected")

    # ── Core operations ────────────────────────────────────────────────────

    def capture_image(self, dest_dir: Path) -> CaptureResult:
        """
        Trigger capture, wait for processing, download, delete from camera.
        Image filename includes UTC timestamp for unambiguous ordering.
        """
        if not self._connected:
            raise CameraError("Not connected — call connect() first")

        self._settings_cache = None
        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc)

        # Use a temp dir inside dest_dir so the atomic rename stays on the
        # same filesystem (avoids cross-device link errors on SSD + tmpfs).
        with tempfile.TemporaryDirectory(dir=dest_dir, prefix=".tmp_capture_") as tmp:
            tmp_path = Path(tmp)

            log.info("Triggering capture…")
            try:
                result = _run(
                    [
                        GPHOTO2_CMD,
                        "--port", self._port,
                        "--capture-image-and-download",
                        "--filename", str(tmp_path / "%Y%m%d_%H%M%S.%C"),
                        "--force-overwrite",
                        "--keep-raw",       # download all files camera produced
                    ],
                    timeout=self._cap_timeout,
                )
            except CameraError as exc:
                raise CaptureFailed(f"Capture failed: {exc}") from exc

            # Find downloaded file(s) — pick largest (RAW > JPG if both exist)
            files = sorted(tmp_path.iterdir(), key=lambda p: p.stat().st_size, reverse=True)
            if not files:
                raise CaptureFailed(
                    f"gphoto2 ran but no file downloaded to {tmp_path}. "
                    f"stdout={result.stdout[:200]}"
                )

            tmp_file = files[0]
            log.info("Downloaded: %s (%d bytes)", tmp_file.name, tmp_file.stat().st_size)

            # Compute hash before moving
            sha256 = _sha256(tmp_file)

            # Build final filename: <kunde>_<site>_<kamera>_<timestamp>.<ext>
            # Fallback til device_id hvis navne ikke er konfigureret
            import re
            def _sanitize(s):
                return re.sub(r'[^A-Za-z0-9æøåÆØÅ]', '_', str(s)).strip('_') if s else ''
            device_id = self._config.get("device_id", "unknown")
            customer  = _sanitize(self._config.get("customer_name", ""))
            site      = _sanitize(self._config.get("site_name", ""))
            camera    = _sanitize(self._config.get("camera_name", ""))
            ts_str    = timestamp.strftime("%Y%m%d_%H%M%S")
            if customer and site and camera:
                final_name = f"{customer}_{site}_{camera}_{ts_str}{tmp_file.suffix}"
            else:
                final_name = f"{device_id}_{ts_str}{tmp_file.suffix}"
            final_path = dest_dir / final_name

            # Atomic rename within same filesystem
            shutil.move(str(tmp_file), str(final_path))

        # Generer sidecar JSON med original SHA-256 FØR XMP
        # Rækkefølge er kritisk: SHA-256 → Sidecar → XMP
        xmp_written = False
        try:
            self._write_sidecar(final_path, sha256, timestamp, False)
        except Exception as exc:
            log.warning("Sidecar JSON fejlede (ikke kritisk): %s", exc)

        # Skriv XMP EFTER sidecar — sha256 i sidecar er af original
        # Quality checker bruger sha256 variablen (pre-XMP) — ingen mismatch
        try:
            xmp_written = self._write_xmp_metadata(final_path, sha256)
            if xmp_written:
                # Opdater sidecar med xmp_written=True
                self._write_sidecar(final_path, sha256, timestamp, True)
        except Exception as exc:
            log.warning("XMP fejlede (ikke kritisk): %s", exc)

        # Delete from camera if configured
        if self._delete_after:
            self._delete_camera_files()

        # Read EXIF-like data from gphoto2 config
        exposure, aperture, iso, focus_mode = self._read_capture_settings()

        return CaptureResult(
            filepath      = final_path,
            timestamp     = timestamp,
            filesize      = final_path.stat().st_size,
            sha256        = sha256,
            camera_model  = self._model or "Unknown Canon DSLR",
            driver_name   = self.driver_name,
            exposure_time = exposure,
            aperture      = aperture,
            iso           = iso,
            focus_mode    = focus_mode,
        )

    def _write_sidecar(self, image_path, sha256: str, timestamp, xmp_written: bool = False) -> None:
        """Skriv metadata sidecar JSON ved siden af billedet.

        INTEGRITET: Original JPEG modificeres ALDRIG.
        SHA-256 beregnes FØR enhver filoperation og gemmes her.
        Sidecar beskriver præcist hvad der er originalt og hvad der er tilføjet.
        """
        import json as _json
        from datetime import timezone as _tz
        from pathlib import Path as _Path

        cfg      = self._config
        loc      = dict(cfg.get("location", {}) or {})
        cam_cfg  = cfg.get("camera", {})
        device   = cfg.get("device", {})
        schedule = cfg.get("schedule", {})
        if loc.get("gps_source") == "gpsd" and (loc.get("gps_lat") is None or loc.get("gps_lon") is None):
            # 2026-07-04: brug det cachede fix (laest mens relaeet var slukket
            # -- se refresh_gps_cache()) i stedet for et live-kald her, da
            # GPS-modtageren mister fix naar kamera-relaeet er taendt (hvilket
            # det altid er paa dette tidspunkt i optagelsen). Foerste optagelse
            # efter opstart, foer cachen er naaet at blive fyldt, forsoger et
            # (formentlig forgaeves) live-kald som fallback.
            if self._last_gps_fix:
                loc.update(self._last_gps_fix)
            else:
                loc.update(_read_gpsd_fix())
        gps_alt = loc.get("gps_alt_m", loc.get("gps_alt"))

        # Hent kamera EXIF parametre (allerede læst)
        exposure, aperture, iso, focus_mode = self._read_capture_settings()

        # Byg sidecar struktur
        sidecar = {
            "timelapse_pro": {
                "version":        "2.2.0",
                "generated_at":   timestamp.astimezone(_tz.utc).isoformat(),
            },

            # ── Integritet ───────────────────────────────────────────────
            "integrity": {
                "sha256_original":      sha256,
                "captured_at_utc":      timestamp.astimezone(_tz.utc).isoformat(),
                "captured_at_local":    timestamp.astimezone(__import__("zoneinfo").ZoneInfo(schedule.get("timezone", "UTC"))).isoformat(),
                "timezone":             schedule.get("timezone", "UTC"),
                "image_file":           image_path.name,
                "original_unmodified":  True,
                "xmp_written":          xmp_written,
                "xmp_note":             "XMP skrevet i JPEG XMP sektion — påvirker ikke billedpixels" if xmp_written else "XMP ikke skrevet",
                "note": "SHA-256 beregnet af rå kamera download inden enhver filbehandling"
            },

            # ── Tilføjet metadata (ikke i original JPEG) ─────────────────
            "added_metadata": {
                "fields_added": [],
                "source":       "TimeLapse Pro konfiguration",
            },

            # ── Lokation og orientering ──────────────────────────────────
            "location": {
                "gps_lat":              loc.get("gps_lat"),
                "gps_lon":              loc.get("gps_lon"),
                "gps_alt_m":            gps_alt,
                "gps_source":           loc.get("gps_source", "manual"),
                "address":              loc.get("address"),
                "azimuth_deg":          cam_cfg.get("azimuth_deg"),
                "tilt_deg":             cam_cfg.get("tilt_deg"),
                "mount_height_m":       cam_cfg.get("mount_height_m"),
                "fov_horizontal_deg":   cam_cfg.get("fov_horizontal_deg"),
                "fov_vertical_deg":     cam_cfg.get("fov_vertical_deg"),
                "perspective":          cam_cfg.get("perspective"),
            },

            # ── Site og projekt ──────────────────────────────────────────
            "project": {
                "customer":     cfg.get("customer_name", "") or device.get("customer_name", ""),
                "site":         cfg.get("site_name", "") or device.get("site_name", ""),
                "camera_name":  cfg.get("camera_name", "") or device.get("camera_name", ""),
                "device_id":    device.get("device_id", ""),
                "camera_index": cam_cfg.get("camera_index", 0),
            },

            # ── Kamera teknisk ───────────────────────────────────────────
            "camera": {
                "model":          self._model or "Unknown",
                "iso":            iso,
                "aperture":       aperture,
                "shutter_speed":  exposure,
                "focus_mode":     focus_mode,
                "gphoto2_port":   self._port,
                "relay_gpio_pin": cam_cfg.get("relay_gpio_pin"),
            },
        }

        # Registrer hvilke felter der er tilføjet (ikke fra kamera)
        added = []
        if loc.get("gps_lat"):
            added.append("gps_lat")
        if loc.get("gps_lon"):
            added.append("gps_lon")
        if gps_alt is not None:
            added.append("gps_alt_m")
        if cam_cfg.get("azimuth_deg") is not None:
            added.append("azimuth_deg")
        if cam_cfg.get("tilt_deg") is not None:
            added.append("tilt_deg")
        if cam_cfg.get("mount_height_m") is not None:
            added.append("mount_height_m")
        if cam_cfg.get("fov_horizontal_deg") is not None:
            added.append("fov_horizontal_deg")
        sidecar["added_metadata"]["fields_added"] = added

        # Skriv sidecar ved siden af billedet
        sidecar_path = image_path.with_suffix('.json')
        with open(sidecar_path, 'w', encoding='utf-8') as f:
            _json.dump(sidecar, f, indent=2, ensure_ascii=False, default=str)

        log.info("Sidecar skrevet: %s (%d tilføjede felter)",
                 sidecar_path.name, len(added))

    def _write_xmp_metadata(self, filepath, sha256_original: str) -> bool:
        """Skriv XMP metadata til JPEG via exiftool.

        INTEGRITET:
        - sha256_original er SHA-256 af ren kamera output (beregnet FØR dette kald)
        - XMP skrives i JPEG XMP sektion — påvirker IKKE billedpixels
        - sha256_original gemmes i XMP så fremtidige systemer kan verificere originalen
        - Returnerer True hvis XMP blev skrevet

        XMP data inkluderer:
        - GPS koordinater (fra site-konfiguration)
        - Orientering (azimuth, tilt, FOV, montagehøjde)
        - Projekt (kunde, site, kamera)
        - Integritet (sha256 af original, version)
        """
        import subprocess
        cfg     = self._config
        loc     = dict(cfg.get("location", {}) or {})
        cam_cfg = cfg.get("camera", {})
        device  = cfg.get("device", {})
        if loc.get("gps_source") == "gpsd" and (loc.get("gps_lat") is None or loc.get("gps_lon") is None):
            # Se kommentar i _write_sidecar() -- brug cachet fix fra idle-tid.
            if self._last_gps_fix:
                loc.update(self._last_gps_fix)
            else:
                loc.update(_read_gpsd_fix())

        cmd = [
            "exiftool",
            "-overwrite_original",
            # Integritet — SHA-256 af original kamera output
            f"-XMP-xmpMM:OriginalDocumentID={sha256_original}",
            f"-XMP-dc:Source=TimeLapse Pro v2.2.0",
            # Projekt metadata
            f"-XMP-dc:Publisher={device.get('customer_name', '')}",
            f"-XMP-dc:Title={device.get('site_name', '')} — {device.get('camera_name', '')}",
            f"-IPTC:By-line={device.get('customer_name', '')}",
            f"-IPTC:CaptionAbstract=TimeLapse Pro | {device.get('customer_name','')} | {device.get('site_name','')} | {device.get('camera_name','')}",
        ]

        # GPS (hvis konfigureret og kamera ikke har GPS)
        gps_lat = loc.get("gps_lat")
        gps_lon = loc.get("gps_lon")
        gps_alt = loc.get("gps_alt_m", loc.get("gps_alt"))
        if gps_lat and gps_lon:
            # Tjek om kamera allerede har GPS
            check = _run_external(
                ["exiftool", "-GPSLatitude", str(filepath)],
                timeout=10,
                label="exiftool",
            )
            if "GPS Latitude" not in check.stdout:
                lat_ref = "N" if gps_lat >= 0 else "S"
                lon_ref = "E" if gps_lon >= 0 else "W"
                cmd += [
                    f"-GPSLatitudeRef={lat_ref}",
                    f"-GPSLatitude={abs(gps_lat):.6f}",
                    f"-GPSLongitudeRef={lon_ref}",
                    f"-GPSLongitude={abs(gps_lon):.6f}",
                ]
                if gps_alt is not None:
                    cmd += [
                        f"-GPSAltitudeRef={'0' if gps_alt >= 0 else '1'}",
                        f"-GPSAltitude={abs(gps_alt):.1f}",
                    ]

        # Custom XMP namespace til orientering
        if cam_cfg.get("azimuth_deg") is not None:
            cmd.append(f"-XMP-aux:Lens=Azimuth:{cam_cfg['azimuth_deg']}deg")
        if cam_cfg.get("tilt_deg") is not None:
            cmd.append(f"-XMP-exifEX:CameraElevationAngle={cam_cfg['tilt_deg']}")

        # Billedrettigheder og beskrivelse
        cmd += [
            f"-XMP-dc:Rights=Copyright {device.get('customer_name', '')}",
            f"-XMP-photoshop:City={loc.get('address', '')}",
            str(filepath)
        ]

        try:
            result = _run_external(cmd, timeout=30, label="exiftool")
            if result.returncode == 0:
                log.info("XMP skrevet: %s (GPS=%s, azimuth=%s)",
                         filepath.name,
                         f"{gps_lat:.4f},{gps_lon:.4f}" if gps_lat else "nej",
                         cam_cfg.get("azimuth_deg", "ej konfigureret"))
                return True
            else:
                log.warning("exiftool XMP fejl: %s", result.stderr.strip())
                return False
        except FileNotFoundError:
            log.warning("exiftool ikke fundet — XMP skipped (apt install exiftool)")
            return False
        except Exception as exc:
            log.warning("XMP fejl: %s", exc)
            return False

    def get_status(self) -> CameraStatus:
        """Return camera status including battery level."""
        try:
            result = _run(
                [GPHOTO2_CMD, "--port", self._port, "--summary"],
                timeout=STATUS_TIMEOUT_S,
                check=False,
            )
            battery = self._parse_battery(result.stdout)
            state = (CameraState.CONNECTED
                     if result.returncode == 0
                     else CameraState.ERROR)
            return CameraStatus(
                state           = state,
                model           = self._model or "Unknown",
                driver          = self.driver_name,
                battery_pct     = battery,
                storage_free_mb = None,   # not easily available via gphoto2
                error_message   = result.stderr.strip() if result.returncode != 0 else None,
                raw             = {"stdout": result.stdout[:500]},
            )
        except Exception as exc:
            return CameraStatus(
                state         = CameraState.ERROR,
                model         = self._model or "Unknown",
                driver        = self.driver_name,
                battery_pct   = None,
                storage_free_mb=None,
                error_message = str(exc),
            )

    def collect_hardware_inventory(self, latest_capture_path: Optional[Path] = None) -> dict:
        """Read live hardware telemetry from the camera for the Headend CMDB.

        Best-effort by design: field availability varies a lot by vendor/
        model over PTP, so any field the camera doesn't report is left as
        None rather than raising. Model/serial/firmware come from the
        standard PTP DeviceInfo dataset (via `gphoto2 --summary`), which is
        generic across brands. Shutter count is NOT standard PTP — Canon
        exposes a live counter at /main/status/shuttercounter, but Nikon
        bodies (including the Z30) only embed it in each image's MakerNotes,
        so it's read via exiftool from the most recently captured file
        instead (pass `latest_capture_path` when called right after a
        capture — no extra relay/USB round-trip needed).
        See headend/migrations/v27_camera_hardware_inventory.sql for the
        research this is grounded in.
        """
        info: dict = {
            "model": None,
            "serial_number": None,
            "firmware_version": None,
            "battery_level_pct": None,
            "storage_free_mb": None,
            "storage_free_images_est": None,
            "shutter_count": None,
            "shutter_count_source": None,
        }

        summary = _run(
            [GPHOTO2_CMD, "--port", self._port, "--summary"],
            timeout=STATUS_TIMEOUT_S, check=False,
        )
        if summary.returncode == 0:
            text = summary.stdout
            info["battery_level_pct"] = self._parse_battery(text)
            model_match = re.search(r"^Model:\s*(.+)$", text, re.MULTILINE)
            if model_match:
                info["model"] = model_match.group(1).strip() or None
            fw_match = re.search(r"^[Dd]evice [Vv]ersion:\s*(.+)$", text, re.MULTILINE)
            if fw_match:
                info["firmware_version"] = fw_match.group(1).strip() or None
            serial_match = re.search(r"^[Ss]erial [Nn]umber:\s*(.+)$", text, re.MULTILINE)
            if serial_match:
                value = serial_match.group(1).strip()
                if value and value.lower() not in ("none", "(null)", "0"):
                    info["serial_number"] = value

        storage = _run(
            [GPHOTO2_CMD, "--port", self._port, "--storage-info"],
            timeout=STATUS_TIMEOUT_S, check=False,
        )
        if storage.returncode == 0:
            mb_match = re.search(r"Free Space \(Bytes\):.*\((\d+)\s*MB\)", storage.stdout)
            if mb_match:
                info["storage_free_mb"] = int(mb_match.group(1))
            images_match = re.search(r"Free Space \(Images\):\s*(-?\d+)", storage.stdout)
            if images_match:
                count = int(images_match.group(1))
                if count >= 0:   # -1 means "camera doesn't report this"
                    info["storage_free_images_est"] = count

        shutter = self.get_config_param("/main/status/shuttercounter")
        raw_shutter = shutter.get("current") if shutter else None
        if raw_shutter not in (None, ""):
            try:
                info["shutter_count"] = int(str(raw_shutter).strip())
                info["shutter_count_source"] = "canon_ptp_shuttercounter"
            except ValueError:
                pass
        elif latest_capture_path and Path(latest_capture_path).exists():
            count, source = _read_shutter_count_from_exif(Path(latest_capture_path))
            if count is not None:
                info["shutter_count"] = count
                info["shutter_count_source"] = source

        return info

    def health_check(self) -> bool:
        """Quick check: can gphoto2 see the camera?"""
        try:
            result = _run(
                [GPHOTO2_CMD, "--auto-detect"],
                timeout=HEALTH_TIMEOUT_S,
                check=False,
            )
            return result.returncode == 0 and "usb" in result.stdout.lower()
        except Exception:
            return False

    # ── Feature detection ──────────────────────────────────────────────────

    def supports_autofocus(self) -> bool:
        """True if the selected gphoto2 camera profile exposes AF drive."""
        # Try camera_capabilities first (new structure), fallback to features (legacy)
        caps = self._profile.get("camera_capabilities") or self._profile.get("features", {})
        return bool(caps.get("autofocus"))

    def supports_liveview(self) -> bool:
        """True if the selected gphoto2 camera profile exposes preview/liveview."""
        # Try camera_capabilities first (new structure), fallback to features (legacy)
        caps = self._profile.get("camera_capabilities") or self._profile.get("features", {})
        return bool(caps.get("liveview"))

    def supports_remote_focus(self) -> bool:
        """True if the selected gphoto2 camera profile exposes focus motor steps."""
        # Try camera_capabilities first (new structure), fallback to features (legacy)
        caps = self._profile.get("camera_capabilities") or self._profile.get("features", {})
        return bool(caps.get("remote_focus"))

    def supports_datetime_sync(self) -> bool:
        """True if the camera can have its internal clock set via gphoto2."""
        caps = self._profile.get("camera_capabilities", {})
        return bool(caps.get("datetime_sync", True))  # Default true for most cameras

    def get_capabilities(self) -> dict:
        """Return full camera capabilities dict for UI/CMDB."""
        return self._profile.get("camera_capabilities", {})

    def sync_camera_datetime(self, dt: Optional[datetime] = None) -> bool:
        """Synchronize camera internal clock with system time or provided datetime.

        Args:
            dt: Optional datetime to set. If None, uses current system UTC time.

        Returns:
            True if sync succeeded, False otherwise.

        IMPORTANT: Camera timestamp is included in EXIF data and affects image
        hash calculation. Sync before capture for accurate timestamps.
        """
        if not self.supports_datetime_sync():
            log.debug("Camera does not support datetime sync")
            return False

        if dt is None:
            dt = datetime.now(timezone.utc)

        # Format datetime for gphoto2: YYYYMMDD HHMMSS
        # Time is always set in camera's local time — we use UTC for consistency
        dt_str = dt.strftime("%Y%m%d %H%M%S")

        log.info("Syncing camera datetime to: %s UTC", dt_str)

        try:
            result = _run(
                [
                    GPHOTO2_CMD,
                    "--port", self._port,
                    "--set-config",
                    f"/main/settings/datetime={dt_str}"
                ],
                timeout=STATUS_TIMEOUT_S,
                check=False,
            )
            success = result.returncode == 0
            if success:
                log.info("Camera datetime synced successfully")
            else:
                log.warning("Camera datetime sync failed: %s", result.stderr.strip())
            return success
        except Exception as exc:
            log.warning("Camera datetime sync error: %s", exc)
            return False

    def get_camera_datetime(self) -> Optional[datetime]:
        """Read camera's internal datetime setting.

        Returns:
            Camera datetime as timezone-aware UTC, or None if unavailable.
        """
        try:
            result = _run(
                [GPHOTO2_CMD, "--port", self._port,
                 "--get-config", "/main/settings/datetime"],
                timeout=STATUS_TIMEOUT_S,
                check=False,
            )
            if result.returncode != 0:
                return None

            match = re.search(r"Current:\s*(\d{8}\s+\d{6})", result.stdout)
            if not match:
                return None

            dt_str = match.group(1)  # YYYYMMDD HHMMSS
            # Parse as naive datetime, treat as UTC (camera convention in TimeLapse Pro)
            dt = datetime.strptime(dt_str, "%Y%m%d %H%M%S")
            return dt.replace(tzinfo=timezone.utc)
        except Exception as exc:
            log.debug("Failed to read camera datetime: %s", exc)
            return None

    def run_autofocus(self) -> bool:
        """Trigger autofocus on cameras that expose an autofocus action."""
        action = self._profile.get("actions", {}).get("autofocus")
        if not action:
            return False
        result = _run(
            [GPHOTO2_CMD, "--port", self._port, "--set-config", f"{action}=1"],
            timeout=STATUS_TIMEOUT_S,
            check=False,
        )
        return result.returncode == 0

    def drive_manual_focus(self, value: str) -> bool:
        """Move focus motor using the camera's own manualfocusdrive choice label."""
        action = self._profile.get("actions", {}).get("manual_focus")
        if not action or not value:
            return False
        for key, context_value in self._profile.get("focus_controls", {}).get("manual_focus_context", {}).items():
            context_result = _run(
                [GPHOTO2_CMD, "--port", self._port, "--set-config", f"{key}={context_value}"],
                timeout=STATUS_TIMEOUT_S,
                check=False,
            )
            if context_result.returncode != 0:
                log.warning(
                    "Manual focus context failed: %s=%s: %s",
                    key,
                    context_value,
                    context_result.stderr.strip(),
                )
                return False
        result = _run(
            [GPHOTO2_CMD, "--port", self._port, "--set-config", f"{action}={value}"],
            timeout=STATUS_TIMEOUT_S,
            check=False,
        )
        return result.returncode == 0

    def get_config_param(self, path: str) -> Optional[dict]:
        """Read and parse one gphoto2 config parameter."""
        if not path:
            return None
        result = _run(
            [GPHOTO2_CMD, "--port", self._port, "--get-config", path],
            timeout=STATUS_TIMEOUT_S,
            check=False,
        )
        if result.returncode != 0:
            return None
        parsed = _parse_gphoto2_config(f"{path}\n{result.stdout}\nEND\n")
        return parsed[0] if parsed else None

    # ── Config / settings ──────────────────────────────────────────────────

    def capture_preview(self, dest_dir: Path) -> Path:
        """
        Capture a low-resolution preview image (no shutter count increment).
        Returns path to saved JPEG (1056x704 on Canon EOS 1300D).
        """
        import tempfile, shutil, time
        dest_dir.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"preview_{ts_str}.jpg"
        # gphoto2 adds 'thumb_' prefix for previews
        tmp_path = dest_dir / f"thumb_{filename}"
        target   = dest_dir / filename
        _run(
            [GPHOTO2_CMD, "--port", self._port,
             "--capture-preview",
             "--filename", str(dest_dir / filename)],
            timeout=15,
        )
        # gphoto2 may save as thumb_<filename>
        if tmp_path.exists() and not target.exists():
            shutil.move(str(tmp_path), str(target))
        elif not target.exists():
            # Find any recently created preview
            previews = sorted(dest_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
            if previews:
                target = previews[-1]
        log.info("Preview captured: %s (%d KB)", target.name, target.stat().st_size // 1024)
        return target

    def get_all_config(self) -> list[dict]:
        """
        Read all camera configuration via gphoto2 --list-all-config.
        Returns list of dicts with keys: path, label, type, current, choices, readonly.
        """
        result = _run(
            [GPHOTO2_CMD, "--port", self._port, "--list-all-config"],
            timeout=30, check=False
        )
        if result.returncode != 0:
            return []
        return _parse_gphoto2_config(result.stdout)

    def get_profile_summary(self) -> dict:
        """Return normalized camera profile/capability information for UI/CMDB."""
        # Get capabilities from new structure, fallback to legacy "features"
        caps = self._profile.get("camera_capabilities") or self._profile.get("features", {})

        return {
            "driver": self.driver_name,
            "profile_key": self._profile_key,
            "profile_name": self._profile.get("name", self._profile_key),
            "description": self._profile.get("description", ""),
            "detected_model": self._model or "Unknown",
            "gphoto2_port": self._port,
            "shutter_rating": self._profile.get("shutter_rating", 100_000),
            # `features` is the UI contract. Keep `camera_capabilities` as the
            # explicit backend name so older CMDB consumers remain compatible.
            "features": dict(caps),
            "camera_capabilities": dict(caps),
            "capture_settings": dict(self._profile.get("capture_settings", {})),
            "config_commands": dict(self._profile.get("config_commands", {})),
            "focus_controls": dict(self._profile.get("focus_controls", {})),
            "actions": dict(self._profile.get("actions", {})),
        }

    def build_config_command(self, cfg_key: str, value: str) -> Optional[str]:
        """Map a logical TimeLapse camera config key to a profile-specific gphoto2 command."""
        command_map = self._profile.get("config_commands", {})
        spec = command_map.get(cfg_key)
        if not spec:
            default_map = {
                "iso": "iso",
                "shutter_speed": "shutterspeed",
                "aperture": "aperture",
                "whitebalance": "whitebalance",
                "picturestyle": "picturestyle",
                "colorspace": "colorspace",
                "imageformat": "imageformat",
                "meteringmode": "meteringmode",
                "exposurecompensation": "exposurecompensation",
            }
            key = default_map.get(cfg_key)
            return f"{key}={value}" if key else None
        if spec.get("skip"):
            return None
        raw_value = "" if value is None else str(value)
        if raw_value in set(spec.get("skip_values", [])):
            return None
        mapped_value = spec.get("value_map", {}).get(raw_value, raw_value)
        path = spec.get("path")
        if not path:
            return None
        return f"{path}={mapped_value}"

    def normalize_initial_commands(self, commands: list[str]) -> list[str]:
        """Translate legacy short gphoto2 commands through the active camera profile."""
        normalized: list[str] = []
        legacy_aliases = {
            "shutterspeed": "shutter_speed",
                "whitebalance": "whitebalance",
                "focusmode": "focusmode",
                "exposurecompensation": "exposurecompensation",
                "iso": "iso",
            "aperture": "aperture",
            "colorspace": "colorspace",
            "imageformat": "imageformat",
        }
        for cmd in commands:
            if "=" not in cmd:
                normalized.append(cmd)
                continue
            key, value = cmd.split("=", 1)
            cfg_key = legacy_aliases.get(key.strip().split("/")[-1].lower())
            if not cfg_key:
                normalized.append(cmd)
                continue
            mapped = self.build_config_command(cfg_key, value.strip())
            if mapped:
                normalized.append(mapped)
            else:
                log.info("Profile %s skipped incompatible camera command: %s", self._profile_key, cmd)
        return normalized

    def set_config(self, key: str, value: str) -> None:
        """Set a camera config value via gphoto2 --set-config."""
        if key and not key.startswith("/"):
            key = f"/main/{key}"
        log.debug("set_config %s = %s", key, value)
        _run(
            [GPHOTO2_CMD, "--port", self._port,
             "--set-config", f"{key}={value}"],
            timeout=STATUS_TIMEOUT_S,
        )
        self._settings_cache = None

    # ── Driver metadata ────────────────────────────────────────────────────

    @property
    def driver_name(self) -> str:
        return "gphoto2"

    @property
    def supported_models(self) -> list[str]:
        return self.SUPPORTED

    # ── Private helpers ────────────────────────────────────────────────────

    def _delete_camera_files(self) -> None:
        """Delete all files from camera memory after download."""
        try:
            _run(
                [GPHOTO2_CMD, "--port", self._port, "--delete-all-files"],
                timeout=DOWNLOAD_TIMEOUT_S,
            )
            log.debug("Camera memory cleared")
        except CameraError as exc:
            # Non-fatal — log and continue
            log.warning("Could not delete camera files: %s", exc)

    def _profile_for_model(self, model: str) -> tuple[str, dict]:
        """Return the first camera profile whose key matches the detected model."""
        model_l = (model or "").lower()
        for key, profile in CAMERA_PROFILES.items():
            if key == "default":
                continue
            if key.lower() in model_l:
                log.info("Using gphoto2 camera profile: %s", key)
                return key, profile
        log.info("Using gphoto2 camera profile: default")
        return "default", CAMERA_PROFILES["default"]

    def _read_config_current(self, paths: list[str]) -> Optional[str]:
        """Read Current from the first working gphoto2 config path."""
        for key in paths:
            try:
                result = _run(
                    [GPHOTO2_CMD, "--port", self._port, "--get-config", key],
                    timeout=STATUS_TIMEOUT_S,
                    check=False,
                )
                if result.returncode != 0:
                    continue
                match = re.search(r"Current:\s*(.+)", result.stdout)
                if match:
                    return match.group(1).strip()
            except Exception:
                continue
        return None

    def _parse_battery(self, summary_text: str) -> Optional[int]:
        """Extract battery percentage from gphoto2 --summary output."""
        # Typical line: "Battery Level: 75%"
        match = re.search(r"[Bb]attery[^:]*:\s*(\d+)\s*%", summary_text)
        if match:
            return int(match.group(1))
        return None

    def _read_capture_settings(self) -> tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
        """
        Read current shutter speed, aperture, ISO, focus mode from camera.
        Returns (exposure, aperture, iso, focus_mode). Any may be None.
        """
        if self._settings_cache is not None:
            return self._settings_cache

        paths = self._profile.get("capture_settings", CAMERA_PROFILES["default"]["capture_settings"])
        exposure   = self._read_config_current(paths.get("exposure_time", []))
        aperture   = self._read_config_current(paths.get("aperture", []))
        iso_str    = self._read_config_current(paths.get("iso", []))
        focus_mode = self._read_config_current(paths.get("focus_mode", []))

        try:
            iso = int(iso_str) if iso_str else None
        except ValueError:
            iso = None

        self._settings_cache = (exposure, aperture, iso, focus_mode)
        return self._settings_cache
