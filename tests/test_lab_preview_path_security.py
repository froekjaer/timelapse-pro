"""SEC-ZAI-01: LAB preview files must remain inside the device LAB root."""

from pathlib import Path

import pytest

from headend.services.path_security import UnsafePath, resolve_lab_preview_path


def test_valid_preview_stays_under_device_root(tmp_path: Path):
    result = resolve_lab_preview_path(tmp_path, "TL-ABC123", "preview_001.jpg")
    assert result == (tmp_path / "_lab" / "TL-ABC123" / "preview_001.jpg").resolve()


def test_valid_thumbnail_stays_under_thumbnail_root(tmp_path: Path):
    result = resolve_lab_preview_path(
        tmp_path, "TL-ABC123", "preview_001.jpg", thumbnail=True
    )
    assert result == (tmp_path / "_lab" / "TL-ABC123" / ".thumbs" / "preview_001.jpg").resolve()


@pytest.mark.parametrize(
    "filename",
    [
        "../headend.env",
        "../../etc/passwd",
        "/etc/passwd",
        "%2e%2e%2fheadend.env",
        "%2Fetc%2Fpasswd",
        "subdir/preview.jpg",
        "subdir\\preview.jpg",
        "..",
        ".",
        "",
        "evil\x00.jpg",
    ],
)
def test_preview_filename_traversal_is_rejected(tmp_path: Path, filename: str):
    with pytest.raises(UnsafePath):
        resolve_lab_preview_path(tmp_path, "TL-ABC123", filename)


@pytest.mark.parametrize("device_id", ["../other", "/tmp/device", "%2e%2e%2fother", ""])
def test_device_component_traversal_is_rejected(tmp_path: Path, device_id: str):
    with pytest.raises(UnsafePath):
        resolve_lab_preview_path(tmp_path, device_id, "preview.jpg")


def test_main_routes_use_confined_resolver_for_image_and_thumbnail():
    source = (Path(__file__).resolve().parents[1] / "headend" / "main.py").read_text(encoding="utf-8")
    section = source[source.index('@app.get("/api/lab/{device_id}/preview-image/{filename}")'):]
    section = section[: section.index('@app.post("/api/admin/devices/{device_id}/lab-clear-command")')]
    assert section.count("resolve_lab_preview_path(") >= 3
    assert '_sftp_base_path() / "_lab" / device_id / filename' not in section
