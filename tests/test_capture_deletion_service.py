import importlib
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


sys.path.insert(0, str(Path(__file__).parents[1] / "headend"))
service = importlib.import_module("services.capture_deletion_service")


@pytest.mark.parametrize("reason", ["defective", "unwanted", "gdpr_request"])
def test_allowed_deletion_reasons(reason: str) -> None:
    assert service.validate_deletion_reason(reason) == reason


@pytest.mark.parametrize("reason", [None, "", "retention_policy", "disk_full"])
def test_automatic_or_missing_reasons_are_rejected(reason: object) -> None:
    with pytest.raises(HTTPException) as exc:
        service.validate_deletion_reason(reason)
    assert exc.value.status_code == 422
