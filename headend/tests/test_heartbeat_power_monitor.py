"""Power-monitor telemetry must survive the Edge-to-Headend contract."""

import database
import main


def test_ina219_heartbeat_fields_map_to_diagnostic_model():
    fields = main._power_monitor_diagnostic_fields({
        "battery_voltage": 12.152,
        "battery_current_a": 0.2143,
        "battery_power_w": 2.576,
        "power_monitor": {
            "driver": "ina219",
            "measurement_scope": "camera",
            "status": "ok",
            "shunt_voltage_mv": 22.29,
        },
    })

    reading = database.Diagnostic(battery_v=12.152, **fields)

    assert reading.battery_v == 12.152
    assert reading.battery_current_a == 0.2143
    assert reading.battery_power_w == 2.576
    assert reading.power_monitor_driver == "ina219"
    assert reading.power_monitor_scope == "camera"
    assert reading.power_monitor_status == "ok"
    assert reading.power_monitor_shunt_mv == 22.29


def test_missing_power_monitor_is_a_nullable_contract():
    fields = main._power_monitor_diagnostic_fields({})

    assert fields == {
        "battery_current_a": None,
        "battery_power_w": None,
        "power_monitor_status": None,
        "power_monitor_driver": None,
        "power_monitor_scope": None,
        "power_monitor_shunt_mv": None,
    }
