"""I2C power monitoring for TimeLapse Pro Edge devices.

The implementation deliberately uses Linux' ``i2c-dev`` interface directly.
Edge devices are commonly offline, so battery monitoring must not depend on a
package being downloaded from PyPI during installation.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol


I2C_SLAVE = 0x0703


class PowerMonitorError(RuntimeError):
    """Base exception for expected power-monitor failures."""


class PowerMonitorConfigurationError(PowerMonitorError):
    """Raised when the centrally supplied sensor configuration is invalid."""


class PowerMonitorUnavailable(PowerMonitorError):
    """Raised when the configured sensor cannot be reached or read."""


@dataclass(frozen=True)
class PowerMonitorReading:
    voltage_v: float
    current_a: float
    power_w: float
    shunt_voltage_mv: float
    overflow: bool

    def as_dict(self) -> dict[str, float | bool]:
        return asdict(self)


@dataclass(frozen=True)
class INA219Config:
    i2c_bus: int = 0
    i2c_address: int = 0x40
    shunt_ohms: float = 0.1
    current_lsb_ma: float = 0.1
    max_bus_voltage_v: float = 26.0
    runtime_dir: Path = Path("/run/timelapse")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "INA219Config":
        try:
            bus = int(value.get("i2c_bus", 0))
            address_value = value.get("i2c_address", "0x40")
            address = (
                int(address_value, 0)
                if isinstance(address_value, str)
                else int(address_value)
            )
            shunt_ohms = float(value.get("shunt_ohms", 0.1))
            current_lsb_ma = float(value.get("current_lsb_ma", 0.1))
            max_bus_voltage_v = float(value.get("max_bus_voltage_v", 26.0))
            runtime_dir = Path(str(value.get("runtime_dir", "/run/timelapse")))
        except (TypeError, ValueError) as exc:
            raise PowerMonitorConfigurationError(
                "INA219 configuration contains a non-numeric value"
            ) from exc

        if bus < 0:
            raise PowerMonitorConfigurationError("i2c_bus must be zero or greater")
        if not 0x03 <= address <= 0x77:
            raise PowerMonitorConfigurationError("i2c_address is outside the I2C range")
        if shunt_ohms <= 0:
            raise PowerMonitorConfigurationError("shunt_ohms must be greater than zero")
        if current_lsb_ma <= 0:
            raise PowerMonitorConfigurationError("current_lsb_ma must be greater than zero")
        if not 0 < max_bus_voltage_v <= 26:
            raise PowerMonitorConfigurationError(
                "INA219 max_bus_voltage_v must be between 0 and 26"
            )

        calibration = int(0.04096 / ((current_lsb_ma / 1000.0) * shunt_ohms))
        if not 1 <= calibration <= 0xFFFF:
            raise PowerMonitorConfigurationError(
                "shunt_ohms/current_lsb_ma produce an invalid calibration register"
            )

        return cls(
            i2c_bus=bus,
            i2c_address=address,
            shunt_ohms=shunt_ohms,
            current_lsb_ma=current_lsb_ma,
            max_bus_voltage_v=max_bus_voltage_v,
            runtime_dir=runtime_dir,
        )

    @property
    def device_path(self) -> Path:
        return Path(f"/dev/i2c-{self.i2c_bus}")

    @property
    def calibration_register(self) -> int:
        return int(0.04096 / ((self.current_lsb_ma / 1000.0) * self.shunt_ohms))


@dataclass(frozen=True)
class INA226Config:
    """Factory calibration for the isolated M5Stack U200 10 A unit."""

    i2c_bus: int = 0
    i2c_address: int = 0x41
    shunt_ohms: float = 0.005
    current_lsb_ma: float = 0.32
    max_bus_voltage_v: float = 30.0
    runtime_dir: Path = Path("/run/timelapse")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "INA226Config":
        try:
            bus = int(value.get("i2c_bus", 0))
            address_value = value.get("i2c_address", "0x41")
            address = (
                int(address_value, 0)
                if isinstance(address_value, str)
                else int(address_value)
            )
            shunt_ohms = float(value.get("shunt_ohms", 0.005))
            current_lsb_ma = float(value.get("current_lsb_ma", 0.32))
            max_bus_voltage_v = float(value.get("max_bus_voltage_v", 30.0))
            runtime_dir = Path(str(value.get("runtime_dir", "/run/timelapse")))
        except (TypeError, ValueError) as exc:
            raise PowerMonitorConfigurationError(
                "INA226 configuration contains a non-numeric value"
            ) from exc

        if bus < 0:
            raise PowerMonitorConfigurationError("i2c_bus must be zero or greater")
        if not 0x03 <= address <= 0x77:
            raise PowerMonitorConfigurationError("i2c_address is outside the I2C range")
        if shunt_ohms <= 0:
            raise PowerMonitorConfigurationError("shunt_ohms must be greater than zero")
        if current_lsb_ma <= 0:
            raise PowerMonitorConfigurationError("current_lsb_ma must be greater than zero")
        if not 0 < max_bus_voltage_v <= 36:
            raise PowerMonitorConfigurationError(
                "INA226 max_bus_voltage_v must be between 0 and 36"
            )

        calibration = int(0.00512 / ((current_lsb_ma / 1000.0) * shunt_ohms))
        if not 1 <= calibration <= 0xFFFF:
            raise PowerMonitorConfigurationError(
                "shunt_ohms/current_lsb_ma produce an invalid calibration register"
            )

        return cls(
            i2c_bus=bus,
            i2c_address=address,
            shunt_ohms=shunt_ohms,
            current_lsb_ma=current_lsb_ma,
            max_bus_voltage_v=max_bus_voltage_v,
            runtime_dir=runtime_dir,
        )

    @property
    def device_path(self) -> Path:
        return Path(f"/dev/i2c-{self.i2c_bus}")

    @property
    def calibration_register(self) -> int:
        return int(0.00512 / ((self.current_lsb_ma / 1000.0) * self.shunt_ohms))


class RegisterBus(Protocol):
    def __enter__(self) -> "RegisterBus": ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...
    def read_u16(self, register: int) -> int: ...
    def write_u16(self, register: int, value: int) -> None: ...


class LinuxI2CRegisterBus:
    """Minimal big-endian register access through Linux ``/dev/i2c-*``."""

    def __init__(self, device_path: Path, address: int):
        self._device_path = device_path
        self._address = address
        self._fd: int | None = None

    def __enter__(self) -> "LinuxI2CRegisterBus":
        try:
            self._fd = os.open(
                self._device_path,
                os.O_RDWR | getattr(os, "O_CLOEXEC", 0),
            )
            fcntl.ioctl(self._fd, I2C_SLAVE, self._address)
        except OSError as exc:
            self.close()
            raise PowerMonitorUnavailable(
                f"cannot open INA219 on {self._device_path} at 0x{self._address:02x}"
            ) from exc
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def read_u16(self, register: int) -> int:
        fd = self._require_open()
        try:
            if os.write(fd, bytes((register & 0xFF,))) != 1:
                raise OSError("short I2C register write")
            raw = os.read(fd, 2)
        except OSError as exc:
            raise PowerMonitorUnavailable(
                f"failed to read INA219 register 0x{register:02x}"
            ) from exc
        if len(raw) != 2:
            raise PowerMonitorUnavailable(
                f"short read from INA219 register 0x{register:02x}"
            )
        return int.from_bytes(raw, byteorder="big", signed=False)

    def write_u16(self, register: int, value: int) -> None:
        fd = self._require_open()
        payload = bytes((register & 0xFF, (value >> 8) & 0xFF, value & 0xFF))
        try:
            if os.write(fd, payload) != len(payload):
                raise OSError("short I2C register write")
        except OSError as exc:
            raise PowerMonitorUnavailable(
                f"failed to write INA219 register 0x{register:02x}"
            ) from exc

    def _require_open(self) -> int:
        if self._fd is None:
            raise PowerMonitorUnavailable("I2C bus is not open")
        return self._fd


class INA219Monitor:
    """Read voltage, current and power from a standard GY-219 module."""

    REG_CONFIG = 0x00
    REG_SHUNT_VOLTAGE = 0x01
    REG_BUS_VOLTAGE = 0x02
    REG_POWER = 0x03
    REG_CURRENT = 0x04
    REG_CALIBRATION = 0x05

    # 32 V range, +/-320 mV shunt, 12-bit bus/shunt ADC, continuous mode.
    CONFIG_32V_CONTINUOUS = 0x399F
    driver_name = "ina219"

    def __init__(
        self,
        config: INA219Config,
        *,
        bus_factory: Callable[[Path, int], RegisterBus] = LinuxI2CRegisterBus,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.config = config
        self._bus_factory = bus_factory
        self._sleep = sleep

    def read(self) -> PowerMonitorReading:
        try:
            with self._bus_factory(
                self.config.device_path, self.config.i2c_address
            ) as bus:
                # Reapply calibration on every poll. A brownout can reset the
                # INA219 without restarting the Edge agent.
                bus.write_u16(self.REG_CONFIG, self.CONFIG_32V_CONTINUOUS)
                bus.write_u16(
                    self.REG_CALIBRATION, self.config.calibration_register
                )
                self._sleep(0.003)

                bus_raw = bus.read_u16(self.REG_BUS_VOLTAGE)
                shunt_raw = _signed_u16(bus.read_u16(self.REG_SHUNT_VOLTAGE))
                current_raw = _signed_u16(bus.read_u16(self.REG_CURRENT))
                power_raw = bus.read_u16(self.REG_POWER)
        except PowerMonitorError:
            raise
        except (OSError, ValueError) as exc:
            raise PowerMonitorUnavailable("INA219 measurement failed") from exc

        voltage_v = (bus_raw >> 3) * 0.004
        if not 0 <= voltage_v <= self.config.max_bus_voltage_v:
            raise PowerMonitorUnavailable(
                f"INA219 bus voltage {voltage_v:.3f} V is outside configured range"
            )

        current_lsb_a = self.config.current_lsb_ma / 1000.0
        reading = PowerMonitorReading(
            voltage_v=round(voltage_v, 3),
            current_a=round(current_raw * current_lsb_a, 4),
            power_w=round(power_raw * current_lsb_a * 20.0, 3),
            shunt_voltage_mv=round(shunt_raw * 0.01, 3),
            overflow=bool(bus_raw & 0x01),
        )
        _write_runtime_snapshot(self.config, self.driver_name, reading)
        return reading


class INA226Monitor:
    """Read the fully isolated M5Stack U200 INA226 10 A monitor."""

    REG_CONFIG = 0x00
    REG_SHUNT_VOLTAGE = 0x01
    REG_BUS_VOLTAGE = 0x02
    REG_POWER = 0x03
    REG_CURRENT = 0x04
    REG_CALIBRATION = 0x05
    REG_MASK_ENABLE = 0x06

    CONFIG_CONTINUOUS = 0x4127
    MATH_OVERFLOW_FLAG = 0x0004
    driver_name = "ina226_m5_10a"

    def __init__(
        self,
        config: INA226Config,
        *,
        bus_factory: Callable[[Path, int], RegisterBus] = LinuxI2CRegisterBus,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.config = config
        self._bus_factory = bus_factory
        self._sleep = sleep

    def read(self) -> PowerMonitorReading:
        try:
            with self._bus_factory(
                self.config.device_path, self.config.i2c_address
            ) as bus:
                bus.write_u16(self.REG_CONFIG, self.CONFIG_CONTINUOUS)
                bus.write_u16(
                    self.REG_CALIBRATION, self.config.calibration_register
                )
                self._sleep(0.003)

                bus_raw = bus.read_u16(self.REG_BUS_VOLTAGE)
                shunt_raw = _signed_u16(bus.read_u16(self.REG_SHUNT_VOLTAGE))
                current_raw = _signed_u16(bus.read_u16(self.REG_CURRENT))
                power_raw = bus.read_u16(self.REG_POWER)
                mask_raw = bus.read_u16(self.REG_MASK_ENABLE)
        except PowerMonitorError:
            raise
        except (OSError, ValueError) as exc:
            raise PowerMonitorUnavailable("INA226 measurement failed") from exc

        voltage_v = bus_raw * 0.00125
        if not 0 <= voltage_v <= self.config.max_bus_voltage_v:
            raise PowerMonitorUnavailable(
                f"INA226 bus voltage {voltage_v:.3f} V is outside configured range"
            )

        current_lsb_a = self.config.current_lsb_ma / 1000.0
        reading = PowerMonitorReading(
            voltage_v=round(voltage_v, 3),
            current_a=round(current_raw * current_lsb_a, 4),
            power_w=round(power_raw * current_lsb_a * 25.0, 3),
            shunt_voltage_mv=round(shunt_raw * 0.0025, 4),
            overflow=bool(mask_raw & self.MATH_OVERFLOW_FLAG),
        )
        _write_runtime_snapshot(self.config, self.driver_name, reading)
        return reading


def create_power_monitor(
    config: Mapping[str, object],
) -> INA219Monitor | INA226Monitor | None:
    if not bool(config.get("enabled", False)):
        return None
    driver = str(config.get("driver", "ina219")).strip().lower()
    if driver == "ina219":
        return INA219Monitor(INA219Config.from_mapping(config))
    if driver in {"ina226", "ina226_m5_10a"}:
        return INA226Monitor(INA226Config.from_mapping(config))
    raise PowerMonitorConfigurationError(
        f"unsupported power monitor driver: {driver}"
    )


def _signed_u16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def _atomic_write(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _write_runtime_snapshot(
    config: INA219Config | INA226Config,
    driver_name: str,
    reading: PowerMonitorReading,
) -> None:
    """Maintain the legacy runtime-file contract for local diagnostics."""
    try:
        config.runtime_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write(
            config.runtime_dir / "battery_voltage",
            f"{reading.voltage_v:.3f}\n",
        )
        _atomic_write(
            config.runtime_dir / "power_monitor.json",
            json.dumps(
                {
                    "driver": driver_name,
                    "i2c_bus": config.i2c_bus,
                    "i2c_address": f"0x{config.i2c_address:02x}",
                    **reading.as_dict(),
                },
                sort_keys=True,
            )
            + "\n",
        )
    except OSError:
        # Telemetry remains valid even if the optional local snapshot is
        # unavailable due to a read-only filesystem or early boot timing.
        pass
