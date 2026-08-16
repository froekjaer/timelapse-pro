"""z.ai P-02: SFTP retries must persist and honor the configured attempt cap."""

from datetime import datetime, timezone
from pathlib import Path

from edge.upload.sftp import MAX_UPLOAD_ATTEMPTS, SFTPTarget, UploadManager
from edge.utils.database import EdgeDatabase


class RetryDb:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.attempts = 0
        self.completed = False
        self.marked = []

    def get_pending_uploads(self, target: str):
        if self.completed:
            return []
        return [{"id": 1, "filepath": str(self.filepath), "upload_attempts": self.attempts}]

    def increment_upload_attempts(self, capture_id: int) -> int:
        assert capture_id == 1
        self.attempts += 1
        return self.attempts

    def mark_uploaded(self, capture_id: int, target: str):
        self.completed = True
        self.marked.append((capture_id, target))

    def log_event(self, *args, **kwargs):
        return None


def _manager(db: RetryDb) -> UploadManager:
    manager = UploadManager({"device": {"device_id": "TL-RETRY"}, "sftp": {}}, db)
    manager._targets = [
        SFTPTarget(
            name="customer_sftp",
            host="sftp.invalid",
            port=22,
            username="camera",
            remote_base="/incoming",
            key_file=Path("/tmp/test-key"),
        )
    ]
    return manager


def test_retry_pending_stops_after_persistent_attempt_cap(tmp_path: Path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    db = RetryDb(image)
    manager = _manager(db)
    calls = []
    manager._upload_to_target = lambda *args, **kwargs: calls.append(args) or False

    for _ in range(MAX_UPLOAD_ATTEMPTS + 5):
        manager.retry_pending("camera-1")

    assert db.attempts == MAX_UPLOAD_ATTEMPTS
    assert len(calls) == MAX_UPLOAD_ATTEMPTS


def test_successful_retry_is_counted_before_completion(tmp_path: Path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    db = RetryDb(image)
    manager = _manager(db)
    manager._upload_to_target = lambda *args, **kwargs: True

    result = manager.retry_pending("camera-1")

    assert db.attempts == 1
    assert db.marked == [(1, "customer_sftp")]
    assert result["customer_sftp"] == 1


def test_edge_database_persists_upload_attempt_count(tmp_path: Path):
    db = EdgeDatabase({"storage": {"db_path": str(tmp_path / "edge.db")}})
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg")
    capture_id = db.insert_capture(
        device_id="TL-RETRY",
        filepath=image,
        sha256="0" * 64,
        captured_at=datetime.now(timezone.utc),
    )

    assert db.increment_upload_attempts(capture_id) == 1
    assert db.increment_upload_attempts(capture_id) == 2
    assert db.get_capture(capture_id)["upload_attempts"] == 2
