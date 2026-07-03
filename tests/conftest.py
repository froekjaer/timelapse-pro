"""
TimeLapse Pro — pytest konfiguration
"""
import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: kræver live headend på TIMELAPSE_TEST_BASE_URL"
    )
