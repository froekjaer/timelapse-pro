"""Unit tests for the extracted supply-monitor telemetry contract."""

import logging

from sqlalchemy import create_engine, inspect, text

from services.power_monitor_telemetry import (
    default_diagnostics_config,
    power_monitor_diagnostic_fields,
    run_power_monitor_migration,
)


def test_missing_power_monitor_maps_to_nullable_fields():
    assert power_monitor_diagnostic_fields({}) == {
        "battery_current_a": None,
        "battery_power_w": None,
        "power_monitor_status": None,
        "power_monitor_driver": None,
        "power_monitor_scope": None,
        "power_monitor_shunt_mv": None,
    }


def test_default_diagnostics_configs_do_not_share_nested_state():
    first = default_diagnostics_config()
    second = default_diagnostics_config()

    first["power_monitor"]["enabled"] = True
    first["collect"].append("test_only")

    assert second["power_monitor"]["enabled"] is False
    assert "test_only" not in second["collect"]


def test_power_monitor_migration_is_additive_and_idempotent():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE diagnostics (id INTEGER PRIMARY KEY)"))

    run_power_monitor_migration(engine, logging.getLogger(__name__))
    run_power_monitor_migration(engine, logging.getLogger(__name__))

    columns = {column["name"] for column in inspect(engine).get_columns("diagnostics")}
    assert {
        "battery_current_a",
        "battery_power_w",
        "power_monitor_status",
        "power_monitor_driver",
        "power_monitor_scope",
        "power_monitor_shunt_mv",
    }.issubset(columns)
