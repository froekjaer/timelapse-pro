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


class _FakeDb:
    """Minimal stand-in for edge/utils/database.py's confirmed-upload queries."""

    def __init__(self, rows):
        self._rows = rows
        self.marked_deleted = []

    def get_confirmed_uploaded_captures_oldest_first(self, limit=500):
        return list(self._rows[:limit])

    def mark_deleted(self, capture_id):
        self.marked_deleted.append(capture_id)


def _make_guard(tmp_path: Path, delete_at_pct=70, min_free_pct=20, usage_sequence=None):
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    guard = CircularBuffer({
        "storage": {
            "local_path": str(capture_dir),
            "circular_buffer_delete_at_pct": delete_at_pct,
            "circular_buffer_min_free_pct": min_free_pct,
        }
    })
    if usage_sequence is not None:
        it = iter(usage_sequence)
        guard._disk_used_pct = lambda: next(it)
    return guard, capture_dir


def test_cleanup_targets_the_trigger_level_not_the_stricter_free_space_floor(tmp_path: Path) -> None:
    """
    Regression test: cleanup must aim to return to circular_buffer_delete_at_pct
    (70%), NOT to 100 - circular_buffer_min_free_pct (80%). The min-free floor is
    a separate, stricter guarantee — treating it as the cleanup target made the
    70% trigger meaningless (deletion never did anything below 80% used).
    """
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    f1 = capture_dir / "a.jpg"
    f1.write_bytes(b"x")
    guard = CircularBuffer({
        "storage": {
            "local_path": str(capture_dir),
            "circular_buffer_delete_at_pct": 70,
            "circular_buffer_min_free_pct": 20,
        }
    })
    # Usage starts at 75% (above the 70% trigger, well below the 80% hard floor).
    # One deletion should bring it back to 69% (<=70% trigger) and stop there —
    # the old buggy logic would have broken immediately without deleting anything,
    # since 75% <= 80% (the old, wrong target).
    # calls: 1) initial trigger check, 2) loop's per-candidate check, 3) final check
    usage = iter([75.0, 75.0, 69.0])
    guard._disk_used_pct = lambda: next(usage)
    db = _FakeDb([{"id": 1, "filepath": str(f1), "uploaded_at": "2026-08-01"}])

    deleted = guard.enforce(db)

    assert deleted == 1
    assert db.marked_deleted == [1]
    assert not f1.exists()


def test_hard_floor_violation_raises_critical_not_the_trigger_level(tmp_path: Path, caplog) -> None:
    """
    If the confirmed-uploaded backlog runs out before usage even returns to the
    70% trigger, that alone should NOT be CRITICAL — only actually breaching the
    stricter min-free hard floor (80% used / 20% free) should escalate.
    """
    import logging

    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    f1 = capture_dir / "a.jpg"
    f1.write_bytes(b"x")
    guard = CircularBuffer({
        "storage": {
            "local_path": str(capture_dir),
            "circular_buffer_delete_at_pct": 70,
            "circular_buffer_min_free_pct": 20,
        }
    })
    # Starts at 85% (above BOTH thresholds). Only one eligible capture exists;
    # after deleting it usage drops to 78% — above the 70% trigger, but still
    # under the 80% hard floor. This must be a WARNING, not CRITICAL.
    usage = iter([85.0, 78.0, 78.0])
    guard._disk_used_pct = lambda: next(usage)
    db = _FakeDb([{"id": 1, "filepath": str(f1), "uploaded_at": "2026-08-01"}])

    with caplog.at_level(logging.WARNING):
        deleted = guard.enforce(db)

    assert deleted == 1
    critical_records = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
    assert not critical_records, "should warn, not escalate to CRITICAL, when only the trigger (not the hard floor) is missed"


def test_headend_accepts_edge_disk_metric_names() -> None:
    source = (Path(__file__).parents[1] / "headend" / "main.py").read_text()
    assert 'diag.get("disk_used_pct", diag.get("ssd_used_pct"))' in source
    assert 'diag.get("disk_free_gb", diag.get("ssd_free_gb"))' in source


def test_headend_capture_delete_requires_controlled_reason() -> None:
    source = (Path(__file__).parents[1] / "headend" / "main.py").read_text()
    bulk = source.index("def delete_captures_bulk(")
    assert "validate_deletion_reason" in source[bulk:bulk + 700]
    assert "deletion_reason" in source[bulk:bulk + 700]
    retention = source.index("def _run_retention_cleanup(")
    assert "deleted_count\": 0" in source[retention:retention + 700]
