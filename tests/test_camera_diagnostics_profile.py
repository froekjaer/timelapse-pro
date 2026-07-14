from edge.diagnostics import camera_diagnostics


def test_profiled_camera_only_checks_effective_enforceable_values(monkeypatch):
    values = {
        "/main/capturesettings/focusmode": "AF-A",
        "/main/imgsettings/iso": "100",
    }
    monkeypatch.setattr(camera_diagnostics, "_read_gphoto2_param", lambda path: values.get(path))

    result = camera_diagnostics.collect_camera_diagnostics(
        "Nikon Z30",
        expected_overrides={},
        non_enforceable_keys={"focusmode"},
        include_fleet_defaults=False,
    )

    assert result["camera_config_drift"] == []
    assert result["camera_config_non_enforceable"] == ["focus_mode"]


def test_profiled_camera_still_detects_explicit_override_drift(monkeypatch):
    monkeypatch.setattr(
        camera_diagnostics,
        "_read_gphoto2_param",
        lambda path: "100" if path == "/main/imgsettings/iso" else None,
    )

    result = camera_diagnostics.collect_camera_diagnostics(
        "Nikon Z30",
        expected_overrides={"iso": "200"},
        include_fleet_defaults=False,
    )

    assert result["camera_config_drift"] == [
        {"param": "iso", "expected": "200", "actual": "100"}
    ]
