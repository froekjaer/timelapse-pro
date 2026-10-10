import io
import tarfile

from headend.tools.edge_image_preflight import REQUIRED_PATHS, inspect_rootfs


def _make_tar(path, members):
    with tarfile.open(path, "w:gz") as tar:
        for name in members:
            info = tarfile.TarInfo("./" + name)
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))


def test_complete_rootfs_passes(tmp_path):
    path = tmp_path / "rootfs.tar.gz"
    _make_tar(path, REQUIRED_PATHS)
    assert inspect_rootfs(path)["status"] == "PASS_PREFLIGHT"


def test_missing_agent_blocks(tmp_path):
    path = tmp_path / "rootfs.tar.gz"
    _make_tar(path, REQUIRED_PATHS[1:])
    result = inspect_rootfs(path)
    assert result["status"] == "BLOCK"
    assert "opt/timelapse/edge/agent.py" in result["missing"]


def test_missing_tar_blocks(tmp_path):
    assert inspect_rootfs(tmp_path / "missing.tar.gz")["status"] == "BLOCK"
