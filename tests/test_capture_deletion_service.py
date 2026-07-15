import importlib
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


sys.path.insert(0, str(Path(__file__).parents[1] / "headend"))
service = importlib.import_module("services.capture_deletion_service")


@pytest.mark.parametrize("reason", ["defective", "unwanted", "gdpr_request", "other"])
def test_allowed_deletion_reasons(reason: str) -> None:
    assert service.validate_deletion_reason(reason) == reason


@pytest.mark.parametrize("reason", [None, "", "retention_policy", "disk_full"])
def test_automatic_or_missing_reasons_are_rejected(reason: object) -> None:
    with pytest.raises(HTTPException) as exc:
        service.validate_deletion_reason(reason)
    assert exc.value.status_code == 422


def test_other_requires_and_preserves_explanation() -> None:
    with pytest.raises(HTTPException):
        service.audit_reason("other", "")
    assert service.audit_reason("other", "Kundens konkrete ønske") == "other:Kundens konkrete ønske"
