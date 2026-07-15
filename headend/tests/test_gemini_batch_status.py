from types import SimpleNamespace
from unittest.mock import MagicMock

from ai.gemini_service import GeminiVisionService


def _service_with_job(job):
    service = GeminiVisionService.__new__(GeminiVisionService)
    service._client = MagicMock()
    service._client.batches.get.return_value = job
    return service


def test_batch_status_reads_object_completion_stats():
    job = SimpleNamespace(
        state=SimpleNamespace(name="RUNNING"),
        completion_stats=SimpleNamespace(successful_count="4", failed_count=1, incomplete_count=2),
    )

    result = _service_with_job(job).get_batch_status("jobs/1")

    assert result["state"] == "RUNNING"
    assert result["progress"] == {"success": 4, "error": 1, "incomplete": 2}


def test_batch_status_reads_camel_case_dict_stats():
    job = SimpleNamespace(
        state="SUCCEEDED",
        completionStats={"successfulCount": 7, "failedCount": 0, "incompleteCount": None},
    )

    result = _service_with_job(job).get_batch_status("jobs/2")

    assert result["progress"] == {"success": 7, "error": 0, "incomplete": None}


def test_batch_status_tolerates_missing_progress():
    job = SimpleNamespace(state=SimpleNamespace(name="PENDING"))

    result = _service_with_job(job).get_batch_status("jobs/3")

    assert result["progress"] is None
