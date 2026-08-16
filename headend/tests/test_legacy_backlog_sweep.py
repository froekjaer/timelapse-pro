"""Tests for headend/services/legacy_backlog_sweep.py.

Pure decision-logic tests: caps, skip conditions, and queue-full
backpressure, using lightweight fakes instead of a real DB/filesystem/AI
worker.
"""
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parents[1]))
from services import legacy_backlog_sweep as sweep  # noqa: E402


@dataclass
class FakeCapture:
    id: int
    device_id: str
    filename: str


def _captures(n: int) -> list:
    return [FakeCapture(id=i, device_id="TL-IMPORT-x", filename=f"{i:03d}.jpg") for i in range(n)]


class FakeQuery:
    """Minimal stand-in for the db.query(Capture).filter(...).order_by(...).limit(...).all() chain."""

    def __init__(self, rows: list):
        self._rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._rows


class FakeDb:
    def __init__(self, rows: list):
        self._rows = rows

    def query(self, _model):
        return FakeQuery(self._rows)


_NOOP_KWARGS = dict(
    find_image=lambda d, f: Path(f"/fake/{f}"),
    thumbs_dir_for=lambda p: p.parent / ".thumbs",
    generate_thumbnail=lambda s, d: (True, None),
    is_valid_jpeg=lambda p: True,
    find_existing_thumbnail=lambda p: None,
    queue_capture_for_analysis=lambda cid: True,
)


# ── sweep_thumbnails ─────────────────────────────────────────────────────────

def test_sweep_thumbnails_generates_missing_ones_and_stops_at_cap() -> None:
    candidates = _captures(10)
    generated_targets = []

    def find_image(device_id, filename):
        return Path(f"/fake/{device_id}/{filename}")

    def thumbs_dir_for(image_path):
        return image_path.parent / ".thumbs"

    def find_existing_thumbnail(image_path):
        return None  # nothing exists yet

    def generate_thumbnail(src, dst):
        generated_targets.append(dst)
        return True, None

    def is_valid_jpeg(path):
        return True

    generated, failed = sweep.sweep_thumbnails(
        candidates,
        find_image=find_image,
        thumbs_dir_for=thumbs_dir_for,
        generate_thumbnail=generate_thumbnail,
        is_valid_jpeg=is_valid_jpeg,
        find_existing_thumbnail=find_existing_thumbnail,
        max_per_run=4,
    )
    assert generated == 4
    assert failed == 0
    assert len(generated_targets) == 4  # stopped at the cap, did not process all 10


def test_sweep_thumbnails_skips_captures_that_already_have_one() -> None:
    candidates = _captures(3)
    calls = []

    generated, failed = sweep.sweep_thumbnails(
        candidates,
        find_image=lambda d, f: Path(f"/fake/{f}"),
        thumbs_dir_for=lambda p: p.parent / ".thumbs",
        generate_thumbnail=lambda s, d: calls.append(d) or (True, None),
        is_valid_jpeg=lambda p: True,
        find_existing_thumbnail=lambda p: Path("/fake/.thumbs/exists.jpg"),  # always "found"
        max_per_run=100,
    )
    assert generated == 0
    assert failed == 0
    assert calls == []  # never even tried to generate


def test_sweep_thumbnails_skips_captures_with_no_file_on_disk() -> None:
    candidates = _captures(3)
    generated, failed = sweep.sweep_thumbnails(
        candidates,
        find_image=lambda d, f: None,  # file missing everywhere
        thumbs_dir_for=lambda p: p.parent / ".thumbs",
        generate_thumbnail=lambda s, d: (True, None),
        is_valid_jpeg=lambda p: True,
        find_existing_thumbnail=lambda p: None,
        max_per_run=100,
    )
    assert generated == 0
    assert failed == 0


def test_sweep_thumbnails_counts_generation_failures_without_stopping() -> None:
    candidates = _captures(3)
    generated, failed = sweep.sweep_thumbnails(
        candidates,
        find_image=lambda d, f: Path(f"/fake/{f}"),
        thumbs_dir_for=lambda p: p.parent / ".thumbs",
        generate_thumbnail=lambda s, d: (False, "disk full"),
        is_valid_jpeg=lambda p: True,
        find_existing_thumbnail=lambda p: None,
        max_per_run=100,
    )
    assert generated == 0
    assert failed == 3  # all three attempted and failed, none silently dropped


def test_sweep_thumbnails_one_bad_candidate_does_not_abort_the_rest() -> None:
    candidates = _captures(3)

    def find_image(device_id, filename):
        if filename == "001.jpg":
            raise RuntimeError("boom")
        return Path(f"/fake/{filename}")

    generated, failed = sweep.sweep_thumbnails(
        candidates,
        find_image=find_image,
        thumbs_dir_for=lambda p: p.parent / ".thumbs",
        generate_thumbnail=lambda s, d: (True, None),
        is_valid_jpeg=lambda p: True,
        find_existing_thumbnail=lambda p: None,
        max_per_run=100,
    )
    assert generated == 2  # 000 and 002 still succeeded
    assert failed == 1


# ── sweep_ai_tags ─────────────────────────────────────────────────────────────

def test_sweep_ai_tags_queues_up_to_the_cap() -> None:
    candidates = _captures(10)
    queued_ids = []

    queued, queue_full = sweep.sweep_ai_tags(
        candidates,
        find_image=lambda d, f: Path(f"/fake/{f}"),
        queue_capture_for_analysis=lambda cid: (queued_ids.append(cid) or True),
        max_per_run=4,
    )
    assert queued == 4
    assert queue_full == 0
    assert queued_ids == [0, 1, 2, 3]  # oldest-first order preserved


def test_sweep_ai_tags_stops_on_first_queue_full_and_reports_it() -> None:
    candidates = _captures(5)
    attempts = []

    def queue_fn(cid):
        attempts.append(cid)
        return cid < 2  # first two succeed, then the queue is "full"

    queued, queue_full = sweep.sweep_ai_tags(
        candidates,
        find_image=lambda d, f: Path(f"/fake/{f}"),
        queue_capture_for_analysis=queue_fn,
        max_per_run=100,
    )
    assert queued == 2
    assert queue_full == 1
    assert attempts == [0, 1, 2]  # stopped immediately after the first failure, not all 5


def test_sweep_ai_tags_skips_captures_with_no_file_on_disk() -> None:
    candidates = _captures(3)
    queued, queue_full = sweep.sweep_ai_tags(
        candidates,
        find_image=lambda d, f: None,
        queue_capture_for_analysis=lambda cid: True,
        max_per_run=100,
    )
    assert queued == 0
    assert queue_full == 0


def test_sweep_ai_tags_one_bad_candidate_does_not_abort_the_rest() -> None:
    candidates = _captures(3)

    def find_image(device_id, filename):
        if filename == "001.jpg":
            raise RuntimeError("boom")
        return Path(f"/fake/{filename}")

    queued, queue_full = sweep.sweep_ai_tags(
        candidates,
        find_image=find_image,
        queue_capture_for_analysis=lambda cid: True,
        max_per_run=100,
    )
    assert queued == 2
    assert queue_full == 0


# ── run_once ─────────────────────────────────────────────────────────────────

def test_run_once_does_nothing_when_disabled() -> None:
    db = FakeDb(_captures(5))
    result = sweep.run_once(db, MagicMock(), enabled=False, thumbnail_lock_locked=False, **_NOOP_KWARGS)
    assert result == {"thumbnails_generated": 0, "thumbnails_failed": 0, "ai_queued": 0, "ai_queue_full": 0}


def test_run_once_processes_both_thumbnails_and_ai_when_enabled() -> None:
    db = FakeDb(_captures(3))
    result = sweep.run_once(db, MagicMock(), enabled=True, thumbnail_lock_locked=False, **_NOOP_KWARGS)
    assert result["thumbnails_generated"] == 3
    assert result["ai_queued"] == 3
    assert result["thumbnails_failed"] == 0
    assert result["ai_queue_full"] == 0


def test_run_once_skips_thumbnails_but_still_does_ai_when_lock_is_held() -> None:
    db = FakeDb(_captures(3))
    result = sweep.run_once(db, MagicMock(), enabled=True, thumbnail_lock_locked=True, **_NOOP_KWARGS)
    assert result["thumbnails_generated"] == 0  # skipped — another generation was already in progress
    assert result["ai_queued"] == 3  # AI queueing is independent of the thumbnail lock
