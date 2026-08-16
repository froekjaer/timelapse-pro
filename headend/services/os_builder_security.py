from __future__ import annotations

import os
import re
from pathlib import Path


_IMAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}$")
_SAFE_ARCH_RE = re.compile(r"^[A-Za-z0-9_.+\-]{1,32}$")


class UnsafeBuilderInput(ValueError):
    """Raised when an OS-builder input cannot safely cross into the container."""


def _scalar(value: object, *, name: str, max_len: int = 512) -> str:
    text = str(value or "")
    if not text or len(text) > max_len or "\x00" in text or "\n" in text or "\r" in text:
        raise UnsafeBuilderInput(f"invalid {name}")
    return text


def _basename(value: object, *, name: str) -> str:
    text = _scalar(value, name=name, max_len=255)
    if text in {".", ".."} or Path(text).name != text or "/" in text or "\\" in text:
        raise UnsafeBuilderInput(f"invalid {name}")
    return text


def _image(value: object) -> str:
    text = _scalar(value, name="container image", max_len=256)
    if not _IMAGE_RE.fullmatch(text):
        raise UnsafeBuilderInput("invalid container image")
    return text


def _architecture(value: object) -> str:
    text = _scalar(value, name="architecture", max_len=32)
    if not _SAFE_ARCH_RE.fullmatch(text):
        raise UnsafeBuilderInput("invalid architecture")
    return text


def secure_builder_dir(path: Path) -> Path:
    """Create a private builder workspace owned by the Headend account."""
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def write_private_builder_file(path: Path, content: str = "") -> Path:
    """Write builder input/output placeholders without world/group write access."""
    path.write_text(content)
    os.chmod(path, 0o600)
    return path


def bundle_container_command(
    *,
    docker: str,
    repo: Path,
    build_root: Path,
    image: str,
    output_name: str,
    plan_name: str,
    device_id: str,
    architecture: str,
    source_ref: str,
    category: str | None,
) -> list[str]:
    """Build docker argv with a fixed shell program and data-only environment values."""
    docker = _scalar(docker, name="docker path", max_len=4096)
    image = _image(image)
    output_name = _basename(output_name, name="output name")
    plan_name = _basename(plan_name, name="plan name")
    device_id = _scalar(device_id, name="device id", max_len=200)
    architecture = _architecture(architecture)
    source_ref = _scalar(source_ref, name="source ref", max_len=512)
    category_value = "" if category is None else _scalar(category, name="category", max_len=100)

    script = (
        "set -euo pipefail; "
        "apt-get update; "
        "apt-get install -y --no-install-recommends python3 ca-certificates; "
        "set -- python3 /repo/headend/tools/build_os_bundle.py "
        "--device-id \"$TL_DEVICE_ID\" "
        "--catalog \"/out/$TL_PLAN_NAME\" "
        "--output \"/out/$TL_OUTPUT_NAME\" "
        "--architecture \"$TL_ARCHITECTURE\" "
        "--source-ref \"$TL_SOURCE_REF\" "
        "--include-dependencies --force; "
        "if [ -n \"$TL_CATEGORY\" ]; then set -- \"$@\" --category \"$TL_CATEGORY\"; fi; "
        "exec \"$@\""
    )
    return [
        docker,
        "run",
        "--rm",
        "--platform",
        "linux/arm64",
        "-e",
        "DEBIAN_FRONTEND=noninteractive",
        "-e",
        "TZ=UTC",
        "-e",
        f"TL_DEVICE_ID={device_id}",
        "-e",
        f"TL_PLAN_NAME={plan_name}",
        "-e",
        f"TL_OUTPUT_NAME={output_name}",
        "-e",
        f"TL_ARCHITECTURE={architecture}",
        "-e",
        f"TL_SOURCE_REF={source_ref}",
        "-e",
        f"TL_CATEGORY={category_value}",
        "-v",
        f"{repo}:/repo:ro",
        "-v",
        f"{build_root}:/out",
        image,
        "bash",
        "-lc",
        script,
    ]


def catalog_container_command(
    *,
    docker: str,
    build_root: Path,
    image: str,
    input_name: str,
    output_name: str,
    architecture: str,
) -> list[str]:
    """Build apt-catalog docker argv without interpolating runtime data into shell source."""
    docker = _scalar(docker, name="docker path", max_len=4096)
    image = _image(image)
    input_name = _basename(input_name, name="input name")
    output_name = _basename(output_name, name="output name")
    architecture = _architecture(architecture)
    script = (
        "set -euo pipefail; "
        "apt-get update >/dev/null; "
        "while IFS=$'\\t' read -r name installed; do "
        "[ -n \"$name\" ] || continue; "
        "candidate=$(apt-cache policy \"$name\" | awk '/Candidate:/ {print $2; exit}'); "
        "[ -n \"$candidate\" ] && [ \"$candidate\" != '(none)' ] || continue; "
        "if dpkg --compare-versions \"$candidate\" gt \"$installed\"; then "
        "repos=$(apt-cache policy \"$name\" | awk -v cand=\"$candidate\" '$1 == cand {getline; print $3; exit}'); "
        "[ -n \"$repos\" ] || repos=ubuntu-builder; "
        "case \"$repos\" in *security*) repo_label=noble-security ;; *updates*) repo_label=noble-updates ;; *) repo_label=\"$repos\" ;; esac; "
        "printf '%s/%s %s %s [upgradable from: %s]\\n' \"$name\" \"$repo_label\" \"$candidate\" \"$TL_ARCHITECTURE\" \"$installed\"; "
        "fi; "
        "done < \"/out/$TL_INPUT_NAME\" > \"/out/$TL_OUTPUT_NAME\""
    )
    return [
        docker,
        "run",
        "--rm",
        "--platform",
        "linux/arm64",
        "-e",
        "DEBIAN_FRONTEND=noninteractive",
        "-e",
        f"TL_INPUT_NAME={input_name}",
        "-e",
        f"TL_OUTPUT_NAME={output_name}",
        "-e",
        f"TL_ARCHITECTURE={architecture}",
        "-v",
        f"{build_root}:/out",
        image,
        "bash",
        "-lc",
        script,
    ]
