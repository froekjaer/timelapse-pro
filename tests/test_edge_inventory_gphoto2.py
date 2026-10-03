"""CMDB inventory must report the real libgphoto2 version (was the CLI line)
and whether gphoto2 is a /usr/local source build (2026-10-01)."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "edge"))
from utils import inventory  # noqa: E402

OUT = """gphoto2 2.5.32

Copyright (c) 2000-2025 Marcus Meissner and others

This version of gphoto2 is using the following software versions and options:
gphoto2         2.5.32         gcc, popt(m), exif, no cdk, no aa, jpeg, readline
libgphoto2      2.5.34         standard camlibs (SKIPPING docupen lumix), gcc, no ltdl, EXIF
libgphoto2_port 0.12.2         iolibs: disk ptpip serial usb1 usbdiskdirect usbscsi
"""


def test_reports_library_version_and_source(monkeypatch):
    monkeypatch.setattr(inventory.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=OUT, stderr=""))
    monkeypatch.setattr(inventory.shutil, "which", lambda name: "/usr/local/bin/gphoto2")
    inv = inventory._software_inventory()
    assert inv["gphoto2"] == "gphoto2 2.5.32"
    assert inv["libgphoto2"] == "libgphoto2 2.5.34"
    assert inv["_gphoto2_source"] == "source-build"
    assert "gphoto2_path" not in inv and "gphoto2_source" not in inv


def test_distro_install(monkeypatch):
    monkeypatch.setattr(inventory.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=OUT, stderr=""))
    monkeypatch.setattr(inventory.shutil, "which", lambda name: "/usr/bin/gphoto2")
    assert inventory._software_inventory()["_gphoto2_source"] == "distro"
