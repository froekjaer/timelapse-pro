"""Headend contract helpers for Edge supply-monitor telemetry."""

from __future__ import annotations

from logging import Logger

from sqlalchemy import text


POWER_MONITOR_CONFIG_DEFAULTS = {
    "enabled": False,
    "driver": "ina226_m5_10a",
    "measurement_scope": "system",
    "i2c_bus": 0,
    "i2c_address": "0x41",
    "shunt_ohms": 0.005,
    "current_lsb_ma": 0.32,
    "max_bus_voltage_v": 30.0,
}


def default_diagnostics_config() -> dict:
    """Return independent defaults for an Edge diagnostics response."""
    return {
        "sync_poll_interval_minutes": 5,
        "update_poll_interval_minutes": 5,
        "inventory_report_interval_hours": 24,
        "collect": [
            "cpu_temperature", "cpu_load", "memory_usage", "disk_usage",
            "connectivity_type", "battery_voltage",
        ],
        "power_monitor": dict(POWER_MONITOR_CONFIG_DEFAULTS),
    }


def power_monitor_diagnostic_fields(diagnostics: dict) -> dict:
    """Map versioned Edge telemetry to nullable Diagnostic model fields."""
    power_monitor = diagnostics.get("power_monitor") or {}
    return {
        "battery_current_a": diagnostics.get("battery_current_a"),
        "battery_power_w": diagnostics.get("battery_power_w"),
        "power_monitor_status": power_monitor.get("status"),
        "power_monitor_driver": power_monitor.get("driver"),
        "power_monitor_scope": power_monitor.get("measurement_scope"),
        "power_monitor_shunt_mv": power_monitor.get("shunt_voltage_mv"),
    }


def serialize_power_monitor_reading(reading) -> dict:
    """Expose nullable supply values consistently in device APIs."""
    return {
        "battery_v": reading.battery_v,
        "battery_current_a": reading.battery_current_a,
        "battery_power_w": reading.battery_power_w,
        "power_monitor_status": reading.power_monitor_status,
        "power_monitor_driver": reading.power_monitor_driver,
        "power_monitor_scope": reading.power_monitor_scope,
        "power_monitor_shunt_mv": reading.power_monitor_shunt_mv,
        "solar_v": reading.solar_v,
    }


def run_power_monitor_migration(engine, log: Logger) -> None:
    """Add the nullable supply-monitor columns to existing installations."""
    columns = (
        ("battery_current_a", "FLOAT"),
        ("battery_power_w", "FLOAT"),
        ("power_monitor_status", "VARCHAR(30)"),
        ("power_monitor_driver", "VARCHAR(50)"),
        ("power_monitor_scope", "VARCHAR(30)"),
        ("power_monitor_shunt_mv", "FLOAT"),
    )
    try:
        with engine.connect() as connection:
            for column, column_type in columns:
                try:
                    connection.execute(text(
                        f"ALTER TABLE diagnostics ADD COLUMN {column} {column_type}"
                    ))
                    connection.commit()
                    log.info("DB migration v15: diagnostics.%s tilfojet", column)
                except Exception:
                    connection.rollback()  # Column already exists.
    except Exception as exc:
        log.warning("DB migration v15 fejl (ikke kritisk): %s", exc)
