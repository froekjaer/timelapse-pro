"""Camera hardware/firmware reading (edge/diagnostics/camera_diagnostics.py),
added 2026-09-01 per Peter: get the physical camera's own hardware/firmware
into CMDB. Canon EOS and Nikon expose the same logical fields under
different PTP config paths — eosserialnumber/firmwareversion are Canon EOS
vendor-extension paths, serialnumber/deviceversion are the generic PTP
DeviceInfo fields most non-EOS cameras (including Nikon) expose instead. See
CAMERA_HARDWARE_PARAMS for the full fallback-path lists.
"""
from edge.diagnostics import camera_diagnostics


def test_reads_canon_style_paths_first(monkeypatch):
    values = {
        "/main/status/manufacturer": "Canon Inc.",
        "/main/status/cameramodel": "Canon EOS 2000D",
        "/main/status/eosserialnumber": "123456789",
        "/main/status/firmwareversion": "1.0.3",
    }
    monkeypatch.setattr(camera_diagnostics, "_read_gphoto2_param", lambda path: values.get(path))

    hardware = camera_diagnostics.read_camera_hardware()

    assert hardware == {
        "manufacturer": "Canon Inc.",
        "model": "Canon EOS 2000D",
        "serial_number": "123456789",
        "firmware_version": "1.0.3",
    }


def test_falls_back_to_generic_ptp_paths_when_eos_paths_are_absent(monkeypatch):
    # Nikon Z30-shaped: no eosserialnumber/firmwareversion, only the generic
    # PTP DeviceInfo fields.
    values = {
        "/main/status/manufacturer": "Nikon Corporation",
        "/main/status/cameramodel": "Nikon Z30",
        "/main/status/serialnumber": "4008675309",
        "/main/status/deviceversion": "1.20",
    }
    monkeypatch.setattr(camera_diagnostics, "_read_gphoto2_param", lambda path: values.get(path))

    hardware = camera_diagnostics.read_camera_hardware()

    assert hardware == {
        "manufacturer": "Nikon Corporation",
        "model": "Nikon Z30",
        "serial_number": "4008675309",
        "firmware_version": "1.20",
    }


def test_missing_fields_are_omitted_not_blanked(monkeypatch):
    monkeypatch.setattr(camera_diagnostics, "_read_gphoto2_param", lambda path: None)

    hardware = camera_diagnostics.read_camera_hardware()

    assert hardware == {}


def test_collect_camera_diagnostics_includes_camera_hardware_key(monkeypatch):
    monkeypatch.setattr(
        camera_diagnostics, "_read_gphoto2_param",
        lambda path: "Nikon Z30" if path == "/main/status/cameramodel" else None,
    )

    result = camera_diagnostics.collect_camera_diagnostics("Nikon Z30", include_fleet_defaults=False)

    assert result["camera_hardware"] == {"model": "Nikon Z30"}
