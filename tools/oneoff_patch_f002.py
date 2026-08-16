from pathlib import Path

path = Path("headend/main.py")
source = path.read_text(encoding="utf-8")


def replace_segment(
    label: str,
    scope_marker: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
    required: tuple[str, ...],
) -> None:
    global source
    if source.count(scope_marker) != 1:
        raise SystemExit(f"{label}: scope marker must occur exactly once")
    scope_start = source.index(scope_marker)
    try:
        start = source.index(start_marker, scope_start)
        end = source.index(end_marker, start)
    except ValueError as exc:
        raise SystemExit(f"{label}: scoped patch markers not found; refusing to patch") from exc
    segment = source[start:end]
    missing = [needle for needle in required if needle not in segment]
    if missing:
        raise SystemExit(f"{label}: expected unsafe legacy markers missing: {missing}; refusing to patch")
    source = source[:start] + replacement + source[end:]


bundle_replacement = '''    from headend.services.os_builder_security import (
        bundle_container_command,
        secure_builder_dir,
        write_private_builder_file,
    )

    build_root = secure_builder_dir(output_path.parent)
    plan_copy = build_root / f"{output_path.name}.plan.json"
    write_private_builder_file(plan_copy, plan_path.read_text())
    repo = _repo_root()
    cmd = bundle_container_command(
        docker=docker,
        repo=repo,
        build_root=build_root,
        image=image,
        output_name=output_path.name,
        plan_name=plan_copy.name,
        device_id=device_id,
        architecture=architecture,
        source_ref=source_ref,
        category=category,
    )
    result = _subprocess.run(cmd, text=True, capture_output=True, timeout=3600)
'''

catalog_replacement = '''    from headend.services.os_builder_security import (
        catalog_container_command,
        secure_builder_dir,
        write_private_builder_file,
    )

    build_root = secure_builder_dir(_os_bundle_store_root().expanduser().resolve() / "_catalog-builder")
    safe_device = _re.sub(r"[^A-Za-z0-9_.-]+", "-", device_id)
    input_path = build_root / f"{safe_device}.installed.tsv"
    output_path = build_root / f"{safe_device}.apt-list.txt"
    lines = []
    for name, version in sorted(installed.items()):
        name_s = str(name).strip()
        version_s = str(version).strip()
        if not name_s or not version_s or "\t" in name_s or "\n" in name_s or "\n" in version_s:
            continue
        lines.append(f"{name_s}\t{version_s}")
    write_private_builder_file(input_path, "\n".join(lines) + "\n")
    write_private_builder_file(output_path, "")
    cmd = catalog_container_command(
        docker=docker,
        build_root=build_root,
        image=image,
        input_name=input_path.name,
        output_name=output_path.name,
        architecture=architecture,
    )
    result = _subprocess.run(cmd, text=True, capture_output=True, timeout=3600)
'''

replace_segment(
    "bundle",
    "def _build_os_bundle_in_mac_container(\n",
    "    build_root = output_path.parent\n",
    "    if result.returncode != 0:\n",
    bundle_replacement,
    (
        "os.chmod(build_root, 0o777)",
        "container_output =",
        "build_os_bundle.py --device-id {device_id!r}",
        "--source-ref {source_ref!r}",
    ),
)
replace_segment(
    "catalog",
    "def _generate_apt_list_from_mac_builder(\n",
    "    build_root = (_os_bundle_store_root().expanduser().resolve() / \"_catalog-builder\")\n",
    "    if result.returncode != 0:\n",
    catalog_replacement,
    (
        "os.chmod(build_root, 0o777)",
        "os.chmod(input_path, 0o666)",
        "os.chmod(output_path, 0o666)",
        "shell = (",
        "{architecture}",
    ),
)

path.write_text(source, encoding="utf-8")
