"""Contract tests for the physical Orange Pi 4 Pro/A733 identity."""

from unittest.mock import patch

from edge.hal.orangepi import OrangePiAdapter
from edge.utils import inventory


class _FakePath:
    files = {
        "/proc/device-tree/compatible": b"xunlong,orangepi-4-pro\\0arm,sun6niw2p1\\0",
        "/proc/cpuinfo": b"",
    }

    def __init__(self, path):
        self.path = str(path)

    def read_bytes(self):
        return self.files[self.path]

    def read_text(self):
        return self.files[self.path].decode()


def test_inventory_reports_a733_from_vendor_device_tree():
    with patch.object(inventory, "Path", _FakePath):
        assert inventory._detect_hardware_model() == ("Orange Pi 4 Pro", "Allwinner A733")


def test_inventory_does_not_guess_rk3588s_from_generic_board_name():
    class GenericPath(_FakePath):
        files = {
            "/proc/device-tree/compatible": b"xunlong,orangepi-4-pro\\0",
            "/proc/cpuinfo": b"",
        }

    with patch.object(inventory, "Path", GenericPath):
        assert inventory._detect_hardware_model() == ("Orange Pi 4 Pro", "Ukendt")


def test_hal_prioritizes_a733_signature_over_generic_4_pro_label():
    adapter = OrangePiAdapter("sun6iw2 xunlong,orangepi-4-pro")

    assert adapter.model_name() == "OrangePi 4 Pro (Allwinner A733, arm64)"
    assert adapter.hal_id() == "orangepi4pro"
    assert adapter.capabilities()["soc"] == "Allwinner A733"
    assert adapter.has_csi() is True


def test_hal_keeps_explicit_legacy_rk3399_identity_distinct():
    adapter = OrangePiAdapter("rockchip rk3399 orangepi 4 pro")

    assert adapter.model_name() == "OrangePi 4 Pro (RK3399, arm64)"
    assert adapter.capabilities()["soc"] == "RK3399"
