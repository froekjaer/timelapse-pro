from pathlib import Path

import pytest

from diagnostics.collector import DiagnosticsCollector
from diagnostics.power_monitor import (
    INA219Config,
    INA219Monitor,
    INA226Config,
    INA226Monitor,
    PowerMonitorConfigurationError,
    PowerMonitorUnavailable,
)


class FakeRegisterBus:
    def __init__(self, registers: dict[int, int]):
        self.registers = registers
        self.writes: list[tuple[int, int]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read_u16(self, register: int) -> int:
        return self.registers[register]

    def write_u16(self, register: int, value: int) -> None:
        self.writes.append((register, value))


def test_ina219_decodes_standard_gy219_measurement(tmp_path):
    fake = FakeRegisterBus(
        {
            INA219Monitor.REG_BUS_VOLTAGE: (3100 << 3) | 0x02,
            INA219Monitor.REG_SHUNT_VOLTAGE: 1234,
            INA219Monitor.REG_CURRENT: 15000,
            INA219Monitor.REG_POWER: 9300,
        }
    )
    config = INA219Config.from_mapping(
        {"runtime_dir": str(tmp_path), "i2c_address": "0x40"}
    )
    monitor = INA219Monitor(
        config,
        bus_factory=lambda _path, _address: fake,
        sleep=lambda _seconds: None,
    )

    reading = monitor.read()

    assert reading.voltage_v == 12.4
    assert reading.current_a == 1.5
    assert reading.power_w == 18.6
    assert reading.shunt_voltage_mv == 12.34
    assert reading.overflow is False
    assert fake.writes == [
        (INA219Monitor.REG_CONFIG, INA219Monitor.CONFIG_32V_CONTINUOUS),
        (INA219Monitor.REG_CALIBRATION, 4096),
    ]
    assert (tmp_path / "battery_voltage").read_text() == "12.400\n"
    assert '"driver": "ina219"' in (tmp_path / "power_monitor.json").read_text()


def test_ina219_preserves_bidirectional_current(tmp_path):
    fake = FakeRegisterBus(
        {
            INA219Monitor.REG_BUS_VOLTAGE: (3400 << 3) | 0x02,
            INA219Monitor.REG_SHUNT_VOLTAGE: 0xFC18,  # -1000 => -10 mV
            INA219Monitor.REG_CURRENT: 0xF448,       # -3000 => -0.3 A
            INA219Monitor.REG_POWER: 0,
        }
    )
    monitor = INA219Monitor(
        INA219Config(runtime_dir=tmp_path),
        bus_factory=lambda _path, _address: fake,
        sleep=lambda _seconds: None,
    )

    reading = monitor.read()

    assert reading.current_a == -0.3
    assert reading.shunt_voltage_mv == -10.0


def test_isolated_m5_ina226_10a_factory_calibration(tmp_path):
    fake = FakeRegisterBus(
        {
            INA226Monitor.REG_BUS_VOLTAGE: 9920,       # 12.400 V
            INA226Monitor.REG_SHUNT_VOLTAGE: 2000,    # 5.000 mV
            INA226Monitor.REG_CURRENT: 3125,          # 1.000 A
            INA226Monitor.REG_POWER: 1550,            # 12.400 W
            INA226Monitor.REG_MASK_ENABLE: 0,
        }
    )
    config = INA226Config.from_mapping({"runtime_dir": str(tmp_path)})
    monitor = INA226Monitor(
        config,
        bus_factory=lambda _path, _address: fake,
        sleep=lambda _seconds: None,
    )

    reading = monitor.read()

    assert config.i2c_address == 0x41
    assert config.shunt_ohms == 0.005
    assert config.current_lsb_ma == 0.32
    assert config.calibration_register == 3200
    assert reading.voltage_v == 12.4
    assert reading.current_a == 1.0
    assert reading.power_w == 12.4
    assert reading.shunt_voltage_mv == 5.0
    assert fake.writes == [
        (INA226Monitor.REG_CONFIG, INA226Monitor.CONFIG_CONTINUOUS),
        (INA226Monitor.REG_CALIBRATION, 3200),
    ]
    assert '"driver": "ina226_m5_10a"' in (
        tmp_path / "power_monitor.json"
    ).read_text()


@pytest.mark.parametrize(
    "config",
    [
        {"i2c_bus": -1},
        {"i2c_address": "not-a-number"},
        {"shunt_ohms": 0},
        {"current_lsb_ma": 0},
        {"max_bus_voltage_v": 27},
    ],
)
def test_ina219_rejects_unsafe_configuration(config):
    with pytest.raises(PowerMonitorConfigurationError):
        INA219Config.from_mapping(config)


def test_ina219_rejects_implausible_bus_voltage(tmp_path):
    fake = FakeRegisterBus(
        {
            INA219Monitor.REG_BUS_VOLTAGE: 6500 << 3,  # 26 V
            INA219Monitor.REG_SHUNT_VOLTAGE: 0,
            INA219Monitor.REG_CURRENT: 0,
            INA219Monitor.REG_POWER: 0,
        }
    )
    monitor = INA219Monitor(
        INA219Config(max_bus_voltage_v=16.0, runtime_dir=tmp_path),
        bus_factory=lambda _path, _address: fake,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(PowerMonitorUnavailable):
        monitor.read()


def test_collector_reports_power_monitor_without_capture_dependency(monkeypatch):
    collector = DiagnosticsCollector({
        "diagnostics": {
            "collect": [],
            "power_monitor": {"measurement_scope": "camera"},
        }
    })

    class Reading:
        voltage_v = 12.61
        current_a = 0.82
        power_w = 10.34
        shunt_voltage_mv = 8.2
        overflow = False

    class Monitor:
        driver_name = "ina219"

        def read(self):
            return Reading()

    collector._power_monitor = Monitor()

    result = collector.collect()

    assert result["battery_voltage"] == 12.61
    assert result["battery_current_a"] == 0.82
    assert result["battery_power_w"] == 10.34
    assert result["power_monitor"] == {
        "driver": "ina219",
        "measurement_scope": "camera",
        "status": "ok",
        "shunt_voltage_mv": 8.2,
    }


def test_collector_is_fail_open_when_sensor_is_missing():
    collector = DiagnosticsCollector({"diagnostics": {"collect": []}})

    class Monitor:
        driver_name = "ina219"

        def read(self):
            raise PowerMonitorUnavailable("test sensor missing")

    collector._power_monitor = Monitor()

    result = collector.collect()

    assert result["battery_voltage"] is None
    assert result["power_monitor"]["status"] == "unavailable"
