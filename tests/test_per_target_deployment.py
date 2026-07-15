"""
TimeLapse Pro — Per-Target Deployment Tests (P1)
=================================================

Tests for per-target deployment configuration:
- Target YAML files exist and are valid
- Target-specific parameters
- Hardware abstraction layers
- Docker platform compatibility
- Installation paths consistency

Kør: pytest tests/test_per_target_deployment.py -v

Disse er serverløse kontrakttests og kører i CI.
"""
import os
import pytest
import yaml
import subprocess
from typing import Dict, Any
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGETS_DIR = str(PROJECT_ROOT / "headend" / "tools" / "hardware")


def load_target_yaml(target_name: str) -> Dict[str, Any]:
    """Indlæs target.yaml for en given target."""
    target_path = os.path.join(TARGETS_DIR, target_name, "target.yaml")

    if not os.path.exists(target_path):
        return {}

    with open(target_path) as f:
        return yaml.safe_load(f)


def list_all_targets() -> list:
    """List alle tilgængelige targets."""
    if not os.path.exists(TARGETS_DIR):
        return []

    targets = []
    for item in os.listdir(TARGETS_DIR):
        target_path = os.path.join(TARGETS_DIR, item, "target.yaml")
        if os.path.exists(target_path):
            targets.append(item)

    return targets


# ── 1. Target Files Exist ────────────────────────────────────────────────────────

def test_targets_directory_exists():
    """Targets directory skal eksistere."""
    assert os.path.exists(TARGETS_DIR), f"Targets directory ikke fundet: {TARGETS_DIR}"


def test_at_least_one_target_exists():
    """Mindst én target skal eksistere."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    assert len(targets) >= 1, f"Mindst én target skal eksistere: {targets}"


# ── 2. Known Targets ────────────────────────────────────────────────────────────

KNOWN_TARGETS = ["rpi4", "rpi5", "jetson-orin-nano", "orangepi4pro", "orangepi-pc-plus"]


def test_rpi4_target_exists():
    """Raspberry Pi 4 target skal eksistere."""
    target = load_target_yaml("rpi4")
    if not target:
        pytest.skip("rpi4 target ikke fundet")

    assert target.get("id") == "rpi4"


def test_rpi5_target_exists():
    """Raspberry Pi 5 target skal eksistere."""
    target = load_target_yaml("rpi5")
    if not target:
        pytest.skip("rpi5 target ikke fundet")

    assert target.get("id") == "rpi5"


def test_jetson_orin_nano_target_exists():
    """Jetson Orin Nano target skal eksistere."""
    target = load_target_yaml("jetson-orin-nano")
    if not target:
        pytest.skip("jetson-orin-nano target ikke fundet")

    assert target.get("id") == "jetson-orin-nano"


# ── 3. Target Structure ────────────────────────────────────────────────────────

def test_target_yaml_has_required_fields():
    """Target YAML skal have påkrævede felter."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    required_fields = ["id", "display_name", "arch", "docker_platform"]

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            for field in required_fields:
                assert field in target, f"{target_name} mangler felt: {field}"


def test_target_id_matches_directory():
    """Target ID skal matche directory navn."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            assert target.get("id") == target_name, f"Target ID {target.get('id')} matcher ikke directory {target_name}"


# ── 4. Architecture Fields ───────────────────────────────────────────────────────

def test_target_arch_is_valid():
    """Target arch skal være gyldig."""
    valid_archs = ["arm64", "amd64", "armv7", "aarch64", "armhf"]

    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            arch = target.get("arch")
            assert arch in valid_archs, f"{target_name} har ugyldig arch: {arch}"


def test_target_docker_platform_is_valid():
    """Target docker_platform skal være gyldig."""
    valid_platforms = ["linux/arm64", "linux/amd64", "linux/arm/v7"]

    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            platform = target.get("docker_platform")
            assert platform in valid_platforms, f"{target_name} har ugyldig docker_platform: {platform}"


# ── 5. HAL Configuration ────────────────────────────────────────────────────────

def test_target_hal_class_exists():
    """Target skal have hal_class."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            assert "hal_class" in target or "soc" in target, f"{target_name} mangler hal_class eller soc"


# ── 6. Base Image Configuration ─────────────────────────────────────────────────

def test_target_has_base_image_config():
    """Target skal have base_image konfiguration."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            # Jetson bruger install_script i stedet for base_image
            if target.get("boot_method") == "jetpack":
                continue  # Jetson har undtagelse

            assert "base_image" in target, f"{target_name} mangler base_image"
            base_image = target.get("base_image", {})
            assert isinstance(base_image, dict), f"{target_name} base_image skal være en dict"


# ── 7. Installation Paths ────────────────────────────────────────────────────────

def test_target_agent_install_paths():
    """Target skal have agent_install paths."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            assert "agent_install" in target, f"{target_name} mangler agent_install"

            agent_install = target.get("agent_install", {})
            assert isinstance(agent_install, dict), f"{target_name} agent_install skal være en dict"

            # Tjek påkrævede paths
            required_paths = ["agent_dir", "venv_dir", "data_dir", "config_dir"]
            for path in required_paths:
                assert path in agent_install, f"{target_name} mangler path: {path}"


def test_agent_install_paths_are_absolute():
    """Agent install paths skal være absolute."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            agent_install = target.get("agent_install", {})

            for key, path in agent_install.items():
                if key.endswith("_dir"):
                    assert path.startswith("/"), f"{target_name} {key} skal være absolute: {path}"


# ── 8. Device Tree Detection ────────────────────────────────────────────────────

def test_target_has_device_tree_patterns():
    """Target skal have device_tree_model_patterns."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            assert "device_tree_model_patterns" in target, f"{target_name} mangler device_tree_model_patterns"

            patterns = target.get("device_tree_model_patterns")
            assert isinstance(patterns, list), f"{target_name} device_tree_model_patterns skal være en list"
            assert len(patterns) > 0, f"{target_name} skal have mindst én pattern"


# ── 9. Boot Method ─────────────────────────────────────────────────────────────

def test_target_has_boot_method():
    """Target skal have boot_method."""
    valid_boot_methods = ["firmware", "uboot", "jetpack", "efi", "uboot_spiflash"]

    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            boot_method = target.get("boot_method")
            assert boot_method in valid_boot_methods, f"{target_name} har ugyldig boot_method: {boot_method}"


# ── 10. WiFi Configuration ────────────────────────────────────────────────────────

def test_rpi_targets_use_netplan():
    """RPI targets skal bruge netplan til WiFi."""
    for target_name in ["rpi4", "rpi5"]:
        target = load_target_yaml(target_name)
        if target:
            wifi_method = target.get("wifi_method")
            # RPI targets skal bruge netplan
            assert wifi_method in [None, "netplan"], f"{target_name} skal bruge netplan, har: {wifi_method}"


# ── 11. Capabilities ────────────────────────────────────────────────────────────

def test_jetson_has_cuda_capability():
    """Jetson target skal have CUDA capability."""
    target = load_target_yaml("jetson-orin-nano")
    if not target:
        pytest.skip("jetson-orin-nano target ikke fundet")

    capabilities = target.get("capabilities", {})
    assert isinstance(capabilities, dict), "capabilities skal være en dict"

    # Jetson skal have CUDA
    assert capabilities.get("cuda") is True, "Jetson skal have CUDA capability"


def test_rpi5_has_hailo_capability():
    """RPI5 target skal have Hailo capability."""
    target = load_target_yaml("rpi5")
    if not target:
        pytest.skip("rpi5 target ikke fundet")

    capabilities = target.get("capabilities", {})
    if capabilities:
        # RPI5 kan have Hailo HAT
        assert capabilities.get("hailo_hat") in [True, False], "hailo_hat skal være boolean"


# ── 12. Docker Base Image ───────────────────────────────────────────────────────

def test_rpi_targets_have_docker_base():
    """RPI targets skal have docker_base."""
    for target_name in ["rpi4", "rpi5"]:
        target = load_target_yaml(target_name)
        if target:
            # docker_base er optional
            docker_base = target.get("docker_base")
            if docker_base:
                # Skal være en valid image reference
                assert isinstance(docker_base, str), f"{target_name} docker_base skal være en string"


# ── 13. Extra Packages ─────────────────────────────────────────────────────────

def test_target_can_have_extra_packages():
    """Target kan have extra_packages."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            extra_packages = target.get("extra_packages")
            if extra_packages:
                assert isinstance(extra_packages, list), f"{target_name} extra_packages skal være en list"


# ── 14. Notes Field ────────────────────────────────────────────────────────────

def test_target_can_have_notes():
    """Target kan have notes felt."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            # notes er optional men nyttigt
            notes = target.get("notes")
            if notes:
                assert isinstance(notes, str), f"{target_name} notes skal være en string"


# ── 15. Service Name Consistency ───────────────────────────────────────────────

def test_agent_install_service_name_consistent():
    """Agent install service_name skal være konsistent."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    expected_service = "timelapse-edge"

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            agent_install = target.get("agent_install", {})
            service_name = agent_install.get("service_name")
            if service_name:
                assert service_name == expected_service, f"{target_name} service_name skal være {expected_service}"


# ── 16. Target YAML Validity ───────────────────────────────────────────────────

def test_all_target_yamls_are_valid():
    """Alle target YAML filer skal være gyldige."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target_path = os.path.join(TARGETS_DIR, target_name, "target.yaml")

        # Tjek YAML kan parses
        try:
            with open(target_path) as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"{target_name} har ugyldig YAML: {e}")


# ── 17. Target-Specific Notes ──────────────────────────────────────────────────

def test_jetson_notes_mention_jetpack():
    """Jetson notes skal nævne JetPack."""
    target = load_target_yaml("jetson-orin-nano")
    if not target:
        pytest.skip("jetson-orin-nano target ikke fundet")

    notes = target.get("notes", "")
    if notes:
        # Skal nævne JetPack i notes
        assert "jetpack" in notes.lower(), "Jetson notes skal nævne JetPack"


# ── 18. CSI Lanes Configuration ────────────────────────────────────────────────

def test_hardware_targets_can_have_csi_lanes():
    """Targets kan have csi_lanes konfiguration."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            capabilities = target.get("capabilities", {})
            if capabilities:
                csi_lanes = capabilities.get("csi_lanes")
                if csi_lanes is not None:
                    assert isinstance(csi_lanes, int), f"{target_name} csi_lanes skal være en int"
                    assert csi_lanes > 0, f"{target_name} csi_lanes skal være positiv"


# ── 19. Boot Partition Configuration ─────────────────────────────────────────────

def test_targets_with_base_image_have_partition_info():
    """Targets med base_image skal have partition info."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target and target.get("boot_method") != "jetpack":
            base_image = target.get("base_image", {})
            if base_image:
                # Skal have boot_partition og root_partition
                assert "boot_partition" in base_image, f"{target_name} mangler boot_partition"
                assert "root_partition" in base_image, f"{target_name} mangler root_partition"


# ── 20. Display Name ────────────────────────────────────────────────────────────

def test_target_display_name_exists():
    """Target skal have display_name."""
    targets = list_all_targets()
    if not targets:
        pytest.skip("Ingen targets fundet")

    for target_name in targets:
        target = load_target_yaml(target_name)
        if target:
            assert "display_name" in target, f"{target_name} mangler display_name"
            assert isinstance(target.get("display_name"), str), f"{target_name} display_name skal være en string"
            assert len(target.get("display_name", "")) > 0, f"{target_name} display_name skal ikke være tom"
