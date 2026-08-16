from pathlib import Path

import pytest

from headend.services.os_builder_security import (
    UnsafeBuilderInput,
    bundle_container_command,
    catalog_container_command,
    secure_builder_dir,
    write_private_builder_file,
)


def test_builder_workspace_is_private(tmp_path: Path):
    path = secure_builder_dir(tmp_path / "builder")
    assert path.stat().st_mode & 0o777 == 0o700


def test_builder_files_are_private(tmp_path: Path):
    path = write_private_builder_file(tmp_path / "input.txt", "secret\n")
    assert path.stat().st_mode & 0o777 == 0o600


def test_bundle_command_keeps_dynamic_values_out_of_shell_source(tmp_path: Path):
    marker = "device; touch /tmp/pwned"
    source_ref = "main; curl attacker"
    category = "security; id"
    cmd = bundle_container_command(
        docker="/usr/bin/docker",
        repo=tmp_path / "repo",
        build_root=tmp_path / "out",
        image="ubuntu:24.04",
        output_name="bundle.tar.zst",
        plan_name="plan.json",
        device_id=marker,
        architecture="arm64",
        source_ref=source_ref,
        category=category,
    )
    shell_source = cmd[-1]
    assert marker not in shell_source
    assert source_ref not in shell_source
    assert category not in shell_source
    assert f"TL_DEVICE_ID={marker}" in cmd
    assert f"TL_SOURCE_REF={source_ref}" in cmd
    assert f"TL_CATEGORY={category}" in cmd


def test_catalog_command_keeps_architecture_out_of_shell_source(tmp_path: Path):
    cmd = catalog_container_command(
        docker="/usr/bin/docker",
        build_root=tmp_path,
        image="ubuntu:24.04",
        input_name="device.installed.tsv",
        output_name="device.apt-list.txt",
        architecture="arm64",
    )
    assert "arm64" not in cmd[-1]
    assert "TL_ARCHITECTURE=arm64" in cmd


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("image", "--privileged"),
        ("image", "ubuntu:24.04\n--privileged"),
        ("output", "../bundle.tar"),
        ("plan", "/tmp/plan.json"),
        ("arch", "arm64;id"),
    ],
)
def test_unsafe_builder_control_values_fail_closed(tmp_path: Path, field: str, value: str):
    kwargs = dict(
        docker="/usr/bin/docker",
        repo=tmp_path / "repo",
        build_root=tmp_path / "out",
        image="ubuntu:24.04",
        output_name="bundle.tar.zst",
        plan_name="plan.json",
        device_id="TL-TEST",
        architecture="arm64",
        source_ref="main",
        category=None,
    )
    if field == "image":
        kwargs["image"] = value
    elif field == "output":
        kwargs["output_name"] = value
    elif field == "plan":
        kwargs["plan_name"] = value
    elif field == "arch":
        kwargs["architecture"] = value
    with pytest.raises(UnsafeBuilderInput):
        bundle_container_command(**kwargs)


def _function_slice(source: str, function_name: str, next_function: str) -> str:
    start = source.index(f"def {function_name}(")
    end = source.index(f"def {next_function}(", start)
    return source[start:end]


def test_main_no_longer_contains_world_writable_or_dynamic_shell_in_reported_f002_builders():
    source = Path("headend/main.py").read_text(encoding="utf-8")
    bundle = _function_slice(source, "_build_os_bundle_in_mac_container", "_human_update_job_error")
    catalog = _function_slice(source, "_generate_apt_list_from_mac_builder", "_generate_apt_list_from_ubuntu_metadata")

    assert "os.chmod(build_root, 0o777)" not in bundle
    assert "build_os_bundle.py --device-id {device_id!r}" not in bundle
    assert "bundle_container_command(" in bundle

    assert "os.chmod(build_root, 0o777)" not in catalog
    assert "os.chmod(input_path, 0o666)" not in catalog
    assert "os.chmod(output_path, 0o666)" not in catalog
    assert "shell = (" not in catalog
    assert "catalog_container_command(" in catalog
