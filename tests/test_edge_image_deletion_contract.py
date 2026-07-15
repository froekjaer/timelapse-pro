from pathlib import Path


ROOT = Path(__file__).parents[1]
MAIN = (ROOT / "headend" / "main.py").read_text()


def test_edge_image_delete_preserves_manifest_and_requires_super_admin() -> None:
    start = MAIN.index('def delete_edge_disk_image(')
    section = MAIN[start:start + 2600]
    assert 'require_role("super_admin")' in section
    assert "manifest_retained" in section
    assert ".manifest.json" not in section
    assert "Event(" in section


def test_edge_image_delete_is_path_and_extension_limited() -> None:
    start = MAIN.index('def delete_edge_disk_image(')
    section = MAIN[start:start + 2600]
    assert "storage_dir not in resolved.parents" in section
    assert '.endswith(".img.gz")' in section
    assert '.endswith(".rootfs.tar.gz")' in section
