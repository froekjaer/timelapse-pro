import importlib.util
from pathlib import Path


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


class _RetentionDb:
    def __init__(self, rows):
        self.rows = rows
        self.marked = []
        self.requested_targets = []

    def local_retention_candidates(self, required_targets, limit=200):
        self.requested_targets.append(list(required_targets))

        def delivered(row):
            checks = {
                "primary": row.get("uploaded_primary", 0),
                "customer_sftp": row.get("uploaded_secondary", 0),
                "backup_sftp": row.get("uploaded_tertiary", 0),
            }
            return all(checks.get(target, checks.get("customer_sftp")) for target in required_targets)

        return [
            row for row in sorted(self.rows, key=lambda r: r["captured_at"])
            if not row.get("local_files_deleted_at") and delivered(row)
        ][:limit]

    def mark_local_files_deleted(self, capture_id, reason):
        self.marked.append((capture_id, reason))
        for row in self.rows:
            if row["id"] == capture_id:
                row["local_files_deleted_at"] = "now"
                row["local_retention_reason"] = reason


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


def test_edge_local_retention_deletes_only_delivered_api_buffer_files(tmp_path: Path) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    old_image = capture_dir / "old.jpg"
    new_image = capture_dir / "new.jpg"
    old_image.write_bytes(b"old-delivered-image")
    old_image.with_suffix(".json").write_bytes(b"sidecar")
    old_image.with_suffix(".jpg.qa.json").write_bytes(b"qa")
    thumb_dir = capture_dir / ".thumbs"
    thumb_dir.mkdir()
    (thumb_dir / old_image.name).write_bytes(b"thumb")
    new_image.write_bytes(b"new-undelivered-image")
    db = _RetentionDb([
        {
            "id": 1,
            "filepath": str(old_image),
            "captured_at": "2026-08-01T00:00:00Z",
            "uploaded_primary": 1,
            "uploaded_secondary": 0,
            "uploaded_tertiary": 0,
        },
        {
            "id": 2,
            "filepath": str(new_image),
            "captured_at": "2026-08-02T00:00:00Z",
            "uploaded_primary": 0,
            "uploaded_secondary": 0,
            "uploaded_tertiary": 0,
        },
    ])
    guard = CircularBuffer({
        "storage": {
            "local_path": str(capture_dir),
            "circular_buffer_bytes": 20,
            "local_retention_low_watermark_pct": 50,
        }
    })

    assert guard.enforce(db) == 1
    assert not old_image.exists()
    assert not old_image.with_suffix(".json").exists()
    assert not old_image.with_suffix(".jpg.qa.json").exists()
    assert not (thumb_dir / old_image.name).exists()
    assert new_image.exists()
    assert db.marked == [(1, "edge_local_fifo_after_required_uploads")]
    assert db.requested_targets == [["primary"]]


def test_edge_local_retention_requires_customer_sftp_when_enabled(tmp_path: Path) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    image = capture_dir / "api-only.jpg"
    image.write_bytes(b"x" * 50)
    db = _RetentionDb([{
        "id": 1,
        "filepath": str(image),
        "captured_at": "2026-08-01T00:00:00Z",
        "uploaded_primary": 1,
        "uploaded_secondary": 0,
        "uploaded_tertiary": 0,
    }])
    guard = CircularBuffer({
        "storage": {"local_path": str(capture_dir), "circular_buffer_bytes": 10},
        "sftp": {"enabled": True, "role": "customer_sftp"},
    })

    assert guard.enforce(db) == 0
    assert image.exists()
    assert db.marked == []
    assert db.requested_targets == [["primary", "customer_sftp"]]


def test_edge_local_retention_requires_backup_sftp_when_enabled(tmp_path: Path) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    image = capture_dir / "customer-only.jpg"
    image.write_bytes(b"x" * 50)
    db = _RetentionDb([{
        "id": 1,
        "filepath": str(image),
        "captured_at": "2026-08-01T00:00:00Z",
        "uploaded_primary": 1,
        "uploaded_secondary": 1,
        "uploaded_tertiary": 0,
    }])
    guard = CircularBuffer({
        "storage": {"local_path": str(capture_dir), "circular_buffer_bytes": 10},
        "sftp": {
            "enabled": True,
            "role": "customer_sftp",
            "backup_sftp": {"enabled": True, "role": "backup_sftp"},
        },
    })

    assert guard.enforce(db) == 0
    assert image.exists()
    assert db.marked == []
    assert db.requested_targets == [["primary", "customer_sftp", "backup_sftp"]]


def test_edge_local_retention_uses_fifo_order(tmp_path: Path) -> None:
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    paths = [capture_dir / f"{name}.jpg" for name in ("old", "middle", "new")]
    for path in paths:
        path.write_bytes(b"x" * 10)
    db = _RetentionDb([
        {"id": 2, "filepath": str(paths[1]), "captured_at": "2026-08-02T00:00:00Z", "uploaded_primary": 1},
        {"id": 3, "filepath": str(paths[2]), "captured_at": "2026-08-03T00:00:00Z", "uploaded_primary": 1},
        {"id": 1, "filepath": str(paths[0]), "captured_at": "2026-08-01T00:00:00Z", "uploaded_primary": 1},
    ])
    guard = CircularBuffer({
        "storage": {
            "local_path": str(capture_dir),
            "circular_buffer_bytes": 25,
            "local_retention_low_watermark_pct": 80,
        }
    })

    assert guard.enforce(db) == 1
    assert not paths[0].exists()
    assert paths[1].exists()
    assert paths[2].exists()
    assert db.marked[0][0] == 1


def test_edge_database_retention_candidates_require_all_targets(tmp_path: Path) -> None:
    db = EdgeDatabase({"storage": {"db_path": str(tmp_path / "edge.db")}})
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    first_id = db.insert_capture(
        device_id="TL-RET",
        filepath=first,
        sha256="a" * 64,
        captured_at=_DB_MODULE.datetime(2026, 8, 1, tzinfo=_DB_MODULE.timezone.utc),
    )
    second_id = db.insert_capture(
        device_id="TL-RET",
        filepath=second,
        sha256="b" * 64,
        captured_at=_DB_MODULE.datetime(2026, 8, 2, tzinfo=_DB_MODULE.timezone.utc),
    )
    db.mark_uploaded(first_id, "primary")
    db.mark_uploaded(second_id, "primary")
    db.mark_uploaded(second_id, "customer_sftp")

    assert [row["id"] for row in db.local_retention_candidates(["primary"])] == [first_id, second_id]
    assert [row["id"] for row in db.local_retention_candidates(["primary", "customer_sftp"])] == [second_id]

    db.mark_local_files_deleted(second_id, "edge_local_fifo_after_required_uploads")
    assert db.local_retention_candidates(["primary", "customer_sftp"]) == []


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
