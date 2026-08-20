import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


_BUFFER_PATH = Path(__file__).parents[1] / "edge" / "capture" / "buffer.py"
_SPEC = importlib.util.spec_from_file_location("timelapse_edge_buffer", _BUFFER_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
CircularBuffer = _MODULE.CircularBuffer

_DB_PATH = Path(__file__).parents[1] / "edge" / "utils" / "database.py"
_DB_SPEC = importlib.util.spec_from_file_location("timelapse_edge_database", _DB_PATH)
assert _DB_SPEC and _DB_SPEC.loader
_DB_MODULE = importlib.util.module_from_spec(_DB_SPEC)
_DB_SPEC.loader.exec_module(_DB_MODULE)
EdgeDatabase = _DB_MODULE.EdgeDatabase


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_db(tmp_path: Path):
    return EdgeDatabase({"storage": {"db_path": str(tmp_path / "edge.db")}})


def _insert(db, capture_dir: Path, name: str, captured_at: datetime, size_bytes: int = 2000):
    path = capture_dir / name
    path.write_bytes(b"x" * size_bytes)
    capture_id = db.insert_capture(
        device_id="TL-TEST", filepath=path, sha256="deadbeef" * 8, captured_at=captured_at,
    )
    return capture_id, path


def _mark_uploaded(db, capture_id: int, hours_ago: float):
    uploaded_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db._connect() as conn:
        conn.execute(
            "UPDATE captures SET uploaded_primary=1, uploaded_at=? WHERE id=?",
            (uploaded_at, capture_id),
        )


# ── Tests ────────────────────────────────────────────────────────────────────

def test_capacity_guard_never_deletes_without_db_session(tmp_path: Path) -> None:
    """No DB session means no way to verify upload status — delete nothing."""
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    image = capture_dir / "capture.jpg"
    image.write_bytes(b"immutable-image-evidence")

    guard = CircularBuffer({
        "storage": {"local_path": str(capture_dir), "circular_buffer_gb": 0}
    })

    assert guard.enforce() == 0
    assert image.read_bytes() == b"immutable-image-evidence"


def test_never_deletes_unuploaded_files_even_when_over_capacity(tmp_path: Path) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    db = _make_db(tmp_path)
    _, path = _insert(db, capture_dir, "a.jpg", datetime(2026, 1, 1, tzinfo=timezone.utc))
    # capture_id never marked uploaded.

    guard = CircularBuffer({"storage": {"local_path": str(capture_dir), "circular_buffer_gb": 0}})
    assert guard.enforce(db) == 0
    assert path.exists()


def test_never_deletes_files_uploaded_too_recently(tmp_path: Path) -> None:
    """Default grace period is 24h — an upload confirmed 1h ago must survive."""
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    db = _make_db(tmp_path)
    capture_id, path = _insert(db, capture_dir, "a.jpg", datetime(2026, 1, 1, tzinfo=timezone.utc))
    _mark_uploaded(db, capture_id, hours_ago=1)

    guard = CircularBuffer({"storage": {"local_path": str(capture_dir), "circular_buffer_gb": 0}})
    assert guard.enforce(db) == 0
    assert path.exists()


def test_deletes_oldest_verified_uploaded_aged_files_first(tmp_path: Path) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    db = _make_db(tmp_path)
    id1, p1 = _insert(db, capture_dir, "1.jpg", datetime(2026, 1, 1, tzinfo=timezone.utc), size_bytes=1_000_000)
    id2, p2 = _insert(db, capture_dir, "2.jpg", datetime(2026, 1, 2, tzinfo=timezone.utc), size_bytes=1_000_000)
    id3, p3 = _insert(db, capture_dir, "3.jpg", datetime(2026, 1, 3, tzinfo=timezone.utc), size_bytes=1_000_000)
    for cid in (id1, id2, id3):
        _mark_uploaded(db, cid, hours_ago=48)

    # 3MB on disk; cap at 2.5MB (target ~2.25MB) so deleting only the oldest
    # 1MB file is enough to get back under target.
    guard = CircularBuffer({
        "storage": {"local_path": str(capture_dir), "circular_buffer_gb": 2_500_000 / 1_073_741_824}
    })
    deleted = guard.enforce(db)

    assert deleted == 1
    assert not p1.exists()  # oldest capture deleted first
    assert p2.exists()
    assert p3.exists()      # newest survives


def test_never_falls_through_to_unverified_file_when_verified_pool_exhausted(tmp_path: Path) -> None:
    """The exact failure class that got deletion banned in the first place:
    old code deleted ALL "uploaded" candidates, and if STILL over target,
    fell through to deleting not-yet-uploaded files too. This must never
    happen — running out of verified candidates means stop, not escalate."""
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    db = _make_db(tmp_path)
    uploaded_id, uploaded_path = _insert(
        db, capture_dir, "uploaded.jpg", datetime(2026, 1, 1, tzinfo=timezone.utc), size_bytes=500_000
    )
    _mark_uploaded(db, uploaded_id, hours_ago=48)
    _, unuploaded_path = _insert(
        db, capture_dir, "unuploaded.jpg", datetime(2026, 1, 2, tzinfo=timezone.utc), size_bytes=5_000_000
    )
    # Deleting the one uploaded file still leaves us over the cap — the
    # not-yet-uploaded file (which dominates total usage) must survive anyway.
    guard = CircularBuffer({
        "storage": {"local_path": str(capture_dir), "circular_buffer_gb": 100_000 / 1_073_741_824}
    })
    guard.enforce(db)

    assert not uploaded_path.exists()
    assert unuploaded_path.exists()


def test_get_deletion_candidates_returns_empty_on_db_error_not_raise(tmp_path: Path, monkeypatch) -> None:
    db = _make_db(tmp_path)

    def _broken_connect(*args, **kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(db, "_connect", _broken_connect)
    assert db.get_deletion_candidates(min_hours_since_upload=24) == []


def test_enforce_survives_broken_db_query_deleting_nothing(tmp_path: Path, monkeypatch) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    db = _make_db(tmp_path)
    capture_id, path = _insert(db, capture_dir, "a.jpg", datetime(2026, 1, 1, tzinfo=timezone.utc))
    _mark_uploaded(db, capture_id, hours_ago=48)

    def _broken_connect(*args, **kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(db, "_connect", _broken_connect)
    guard = CircularBuffer({"storage": {"local_path": str(capture_dir), "circular_buffer_gb": 0}})
    assert guard.enforce(db) == 0
    assert path.exists()


def test_stops_at_hysteresis_target_not_the_hard_limit(tmp_path: Path) -> None:
    """Should not delete more than necessary to reach the 90% hysteresis target."""
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    db = _make_db(tmp_path)
    ids_paths = []
    for i in range(5):
        cid, p = _insert(
            db, capture_dir, f"{i}.jpg",
            datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i),
            size_bytes=1_000_000,
        )
        _mark_uploaded(db, cid, hours_ago=48)
        ids_paths.append(p)

    # 5MB on disk, cap at ~4.5MB so it's just barely over — should only need
    # to delete the single oldest file to reach the ~4.05MB (90%) target.
    guard = CircularBuffer({
        "storage": {"local_path": str(capture_dir), "circular_buffer_gb": 4_500_000 / 1_073_741_824}
    })
    deleted = guard.enforce(db)

    assert deleted == 1
    assert not ids_paths[0].exists()
    for p in ids_paths[1:]:
        assert p.exists()


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
