"""
TimeLapse Pro — pytest konfiguration
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: kræver live headend på TIMELAPSE_TEST_BASE_URL"
    )
    config.addinivalue_line(
        "markers", "smoke: hurtig daglig/CI smoke-test for kernefunktionalitet"
    )
    config.addinivalue_line(
        "markers", "unit: unit test der ikke kræver ekstern dependencies"
    )
