"""
TimeLapse Pro — pytest konfiguration
"""
import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: kræver live headend på 192.168.86.132"
    )
