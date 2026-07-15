import importlib.util
from pathlib import Path


_BUFFER_PATH = Path(__file__).parents[1] / "edge" / "capture" / "buffer.py"
_SPEC = importlib.util.spec_from_file_location("timelapse_edge_buffer", _BUFFER_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
CircularBuffer = _MODULE.CircularBuffer


def test_capacity_guard_never_deletes_images(tmp_path: Path) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    image = capture_dir / "capture.jpg"
    image.write_bytes(b"immutable-image-evidence")

    guard = CircularBuffer({
        "storage": {"local_path": str(capture_dir), "circular_buffer_gb": 0}
    })

    assert guard.enforce() == 0
    assert image.read_bytes() == b"immutable-image-evidence"


def test_headend_accepts_edge_disk_metric_names() -> None:
    source = (Path(__file__).parents[1] / "headend" / "main.py").read_text()
    assert 'diag.get("disk_used_pct", diag.get("ssd_used_pct"))' in source
    assert 'diag.get("disk_free_gb", diag.get("ssd_free_gb"))' in source


def test_headend_capture_delete_endpoints_are_blocked() -> None:
    source = (Path(__file__).parents[1] / "headend" / "main.py").read_text()
    single = source.index("def delete_capture(")
    bulk = source.index("def delete_captures_bulk(")
    assert "status_code=409" in source[single:single + 500]
    assert "status_code=409" in source[bulk:bulk + 500]
    retention = source.index("def _run_retention_cleanup(")
    assert "deleted_count\": 0" in source[retention:retention + 700]
