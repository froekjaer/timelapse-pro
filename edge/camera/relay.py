"""
TimeLapse Pro — GPIO Relay Controller (Dual Channel)
=====================================================
Controls both relays on the HW-383A 5V dual-channel relay module.

Supports two hardware backends — auto-detected at runtime:

  rk3588  (Orange Pi 4 Pro)   → _SysfsGPIO  (direct sysfs, no library)
  h3      (Orange Pi PC Plus)  → _OpiGPIO    (OPi.GPIO, BOARD numbering)

Pin mapping:
  Platform   Relay    Physical pin   GPIO id
  --------   ------   ------------   --------
  rk3588     camera   pin 7          GPIO 356
  rk3588     modem    pin 11         GPIO 361
  h3         camera   pin 7          BOARD 7 (PA6)
  h3         modem    —              not fitted

HW-383A is active-low: GPIO LOW = relay ON = load powered.

SABSA: Availability — camera only powered during capture window
                      modem can be power-cycled without physical access
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

GPIO_ROOT = Path("/sys/class/gpio")
# HW-383A active-low: "0" = relay ON, "1" = relay OFF
_RELAY_ON  = "0"
_RELAY_OFF = "1"


# ── Platform detection ────────────────────────────────────────────────────────

def _detect_platform() -> str:
    """Returns 'rk3588' or 'h3' based on /proc/cpuinfo."""
    try:
        info = Path("/proc/cpuinfo").read_text()
        if "RK3588" in info:
            return "rk3588"
        if "Allwinner" in info or "sun8i" in info:
            return "h3"
    except OSError:
        pass
    log.warning("Unknown platform — defaulting to rk3588 (sysfs)")
    return "rk3588"


PLATFORM = _detect_platform()
log.info("GPIO platform: %s", PLATFORM)

# Default GPIO pins per platform
_DEFAULTS = {
    "rk3588": {"camera_pin": 356, "modem_pin": 361},
    "h3":     {"camera_pin": 7,   "modem_pin": None},   # modem not fitted on PC Plus
}


# ── Backend: sysfs (RK3588S) ──────────────────────────────────────────────────

class _SysfsGPIO:
    """Direct sysfs GPIO driver — no library dependency."""

    def __init__(self, pins: list[int], simulate: bool):
        self._simulate = simulate
        self._pins     = pins
        if not simulate:
            self._init(pins)

    def _init(self, pins: list[int]) -> None:
        for pin in pins:
            try:
                self._export(pin)
                self._set_direction(pin, "out")
                self._write(pin, _RELAY_OFF)   # safe state: OFF
                log.debug("sysfs GPIO %d initialised → OFF", pin)
            except Exception as exc:
                log.error("Failed to init GPIO %d: %s", pin, exc)

    def _export(self, pin: int) -> None:
        gpio_dir = GPIO_ROOT / f"gpio{pin}"
        if gpio_dir.exists():
            log.debug("GPIO %d already exported", pin)
            return
        try:
            (GPIO_ROOT / "export").write_text(str(pin))
            time.sleep(0.1)
        except OSError as exc:
            if "517" in str(exc) or "busy" in str(exc).lower():
                log.debug("GPIO %d already exported (busy)", pin)
            else:
                raise

    def _unexport(self, pin: int) -> None:
        try:
            (GPIO_ROOT / "unexport").write_text(str(pin))
        except OSError:
            pass

    def _set_direction(self, pin: int, direction: str) -> None:
        (GPIO_ROOT / f"gpio{pin}" / "direction").write_text(direction)

    def _write(self, pin: int, value: str) -> None:
        (GPIO_ROOT / f"gpio{pin}" / "value").write_text(value)

    def set(self, pin: int, energise: bool) -> None:
        """energise=True → relay ON (active-low: write 0)."""
        if self._simulate:
            log.info("[SIMULATE] GPIO %d → %s", pin, "ON" if energise else "OFF")
            return
        value = _RELAY_ON if energise else _RELAY_OFF
        try:
            self._write(pin, value)
        except Exception as exc:
            log.error("GPIO %d write failed: %s", pin, exc)

    def cleanup(self, pins: list[int]) -> None:
        if self._simulate:
            return
        for pin in pins:
            try:
                self._write(pin, _RELAY_OFF)
                self._unexport(pin)
            except Exception:
                pass


# ── Backend: OPi.GPIO (Allwinner H3) ─────────────────────────────────────────

class _OpiGPIO:
    """OPi.GPIO backend — BOARD numbering, for Orange Pi PC Plus (H3)."""

    def __init__(self, pins: list[int], simulate: bool):
        self._simulate = simulate
        self._pins     = pins
        self._GPIO     = None
        if not simulate:
            self._init(pins)

    def _init(self, pins: list[int]) -> None:
        try:
            import OPi.GPIO as GPIO
            self._GPIO = GPIO
            GPIO.setmode(GPIO.BOARD)
            GPIO.setwarnings(False)
            for pin in pins:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)   # active-low: HIGH = OFF (safe state)
                log.debug("OPi.GPIO BOARD pin %d initialised → OFF", pin)
        except Exception as exc:
            log.error("OPi.GPIO init failed: %s", exc)

    def set(self, pin: int, energise: bool) -> None:
        """energise=True → relay ON (active-low: GPIO.LOW)."""
        if self._simulate:
            log.info("[SIMULATE] OPi BOARD pin %d → %s", pin, "ON" if energise else "OFF")
            return
        try:
            level = self._GPIO.LOW if energise else self._GPIO.HIGH
            self._GPIO.output(pin, level)
        except Exception as exc:
            log.error("OPi.GPIO pin %d write failed: %s", pin, exc)

    def cleanup(self, pins: list[int]) -> None:
        if self._simulate:
            return
        try:
            for pin in pins:
                self._GPIO.output(pin, self._GPIO.HIGH)   # safe state before cleanup
            self._GPIO.cleanup()
        except Exception:
            pass


# ── Relay channel classes (platform-agnostic) ─────────────────────────────────

class CameraRelay:
    """
    Relay 1 — controls camera power.
    Pin is platform-dependent (see _DEFAULTS).

    Config keys (camera section):
        relay_gpio_pin:          int   GPIO/BOARD pin (platform default if omitted)
        relay_on_seconds_before: int   warm-up after power-on (default 10)
        relay_off_seconds_after: int   settle before power-off (default 5)
    """

    def __init__(self, backend: _SysfsGPIO | _OpiGPIO, config: dict, pin: int):
        self._be     = backend
        self._pin    = pin
        self._warmup = int(config.get("relay_on_seconds_before", 10))
        self._settle = int(config.get("relay_off_seconds_after", 5))
        self._on     = False

    def power_on(self) -> None:
        if self._on:
            log.debug("Camera relay already ON")
            return
        log.info("Camera relay ON (pin %d)", self._pin)
        self._be.set(self._pin, True)
        self._on = True
        if self._warmup > 0:
            log.info("Waiting %ds for camera warm-up…", self._warmup)
            time.sleep(self._warmup)

    def power_off(self) -> None:
        if not self._on:
            log.debug("Camera relay already OFF")
            return
        if self._settle > 0:
            log.info("Waiting %ds for camera settle…", self._settle)
            time.sleep(self._settle)
        log.info("Camera relay OFF (pin %d)", self._pin)
        self._be.set(self._pin, False)
        self._on = False

    def force_off(self) -> None:
        log.warning("Camera relay FORCE OFF (pin %d)", self._pin)
        self._be.set(self._pin, False)
        self._on = False

    @property
    def is_on(self) -> bool:
        return self._on

    def __enter__(self):
        self.power_on()
        return self

    def __exit__(self, *_):
        self.power_off()


class ModemRelay:
    """
    Relay 2 — controls 5G USB modem power.
    Only fitted on rk3588 (Orange Pi 4 Pro). Physical pin 11 = GPIO 361.

    Config keys (modem section):
        modem_relay_gpio_pin:        int   sysfs GPIO number (default 361)
        modem_power_cycle_off_s:     int   seconds off during cycle (default 5)
        modem_power_cycle_recover_s: int   recovery wait (default 15)
    """

    DEFAULT_PIN       = 361
    DEFAULT_OFF_S     = 5
    DEFAULT_RECOVER_S = 15

    def __init__(self, backend: _SysfsGPIO | _OpiGPIO, config: dict, pin: int):
        self._be        = backend
        self._pin       = pin
        modem_cfg       = config.get("modem", {})
        self._off_s     = int(modem_cfg.get("modem_power_cycle_off_s", self.DEFAULT_OFF_S))
        self._recover_s = int(modem_cfg.get("modem_power_cycle_recover_s", self.DEFAULT_RECOVER_S))
        self._on        = False
        self._startup()

    def _startup(self) -> None:
        log.info("Modem relay ON at startup (pin %d)", self._pin)
        self._be.set(self._pin, True)
        self._on = True

    def power_cycle(self, reason: str = "manual") -> None:
        log.warning("Modem power-cycle (pin %d) — reason: %s", self._pin, reason)
        self._be.set(self._pin, False)
        self._on = False
        log.info("Modem OFF — waiting %ds…", self._off_s)
        time.sleep(self._off_s)
        self._be.set(self._pin, True)
        self._on = True
        log.info("Modem ON — waiting %ds for registration…", self._recover_s)
        time.sleep(self._recover_s)
        log.info("Modem power-cycle complete")

    def force_off(self) -> None:
        log.info("Modem relay OFF (pin %d)", self._pin)
        self._be.set(self._pin, False)
        self._on = False

    @property
    def is_on(self) -> bool:
        return self._on


class _NoModem:
    """Null-object for platforms without a modem relay (e.g. PC Plus)."""
    is_on = False

    def power_cycle(self, reason: str = "") -> None:
        log.info("_NoModem: power_cycle ignored (%s)", reason)

    def force_off(self) -> None:
        log.info("_NoModem: force_off ignored")


class RelayController:
    """
    Top-level relay manager for HW-383A dual-channel module.
    Auto-detects platform (rk3588/h3) and selects GPIO backend.

    rk3588 (Orange Pi 4 Pro):  sysfs, camera GPIO 356, modem GPIO 361
    h3     (Orange Pi PC Plus): OPi.GPIO BOARD, camera pin 7, no modem

    Set relay_simulate: true in config to skip GPIO entirely.
    """

    def __init__(self, config: dict):
        cam_cfg  = config.get("camera", {})
        simulate = cam_cfg.get("relay_simulate", False)
        defaults = _DEFAULTS[PLATFORM]

        cam_pin   = int(cam_cfg.get("relay_gpio_pin", defaults["camera_pin"]))
        modem_pin = defaults["modem_pin"]
        if modem_pin is not None:
            modem_pin = int(config.get("modem", {}).get("modem_relay_gpio_pin", modem_pin))

        # Select backend
        active_pins = [cam_pin] + ([modem_pin] if modem_pin is not None else [])
        if PLATFORM == "rk3588":
            self._backend = _SysfsGPIO(pins=active_pins, simulate=simulate)
        else:
            self._backend = _OpiGPIO(pins=active_pins, simulate=simulate)

        self.camera = CameraRelay(self._backend, cam_cfg, cam_pin)

        if modem_pin is not None:
            self.modem = ModemRelay(self._backend, config, modem_pin)
        else:
            self.modem = _NoModem()

        self._connectivity = ConnectivityMonitor(self.modem, config)

        log.info(
            "RelayController ready — platform=%s camera_pin=%d modem_pin=%s simulate=%s",
            PLATFORM, cam_pin, modem_pin, simulate
        )

    @property
    def connectivity(self) -> "ConnectivityMonitor":
        return self._connectivity

    def cleanup(self) -> None:
        log.info("RelayController cleanup")
        self.camera.force_off()
        self.modem.force_off()
        pins = [self.camera._pin]
        if not isinstance(self.modem, _NoModem):
            pins.append(self.modem._pin)
        self._backend.cleanup(pins)


class ConnectivityMonitor:
    """
    Watches network connectivity and triggers modem power-cycle
    automatically when failures exceed the configured threshold.
    """

    def __init__(self, modem_relay: ModemRelay | _NoModem, config: dict):
        modem_cfg          = config.get("modem", {})
        self._relay        = modem_relay
        self._max_failures = int(modem_cfg.get("modem_cycle_after_failures", 3))
        self._min_interval = int(modem_cfg.get("modem_min_cycle_interval_s", 600))
        self._failures     = 0
        self._last_cycle_t = 0.0

    def report_success(self) -> None:
        if self._failures > 0:
            log.debug("Connectivity restored after %d failures", self._failures)
        self._failures = 0

    def report_failure(self) -> None:
        self._failures += 1
        log.debug("Connectivity failure %d/%d", self._failures, self._max_failures)
        if self._failures < self._max_failures:
            return
        now        = time.monotonic()
        since_last = now - self._last_cycle_t
        if since_last < self._min_interval:
            log.info("Modem cycle suppressed — %.0fs since last (min %ds)",
                     since_last, self._min_interval)
            return
        log.warning("%d consecutive failures — power-cycling modem", self._failures)
        self._relay.power_cycle(reason=f"{self._failures} consecutive failures")
        self._failures     = 0
        self._last_cycle_t = time.monotonic()

    @property
    def consecutive_failures(self) -> int:
        return self._failures
