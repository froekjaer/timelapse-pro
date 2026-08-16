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


def test_main_no_longer_contains_world_writable_builder_permissions_or_dynamic_builder_shell():
    source = Path("headend/main.py").read_text(encoding="utf-8")
    assert "os.chmod(build_root, 0o777)" not in source
    assert "os.chmod(input_path, 0o666)" not in source
    assert "os.chmod(output_path, 0o666)" not in source
    assert "bundle_container_command(" in source
    assert "catalog_container_command(" in source
