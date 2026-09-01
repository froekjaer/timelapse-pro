from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from headend.redaction_api import _ensure_capture_access, _false_positive_review_payload, _require_role


class _NoFallbackDb:
    """DB sentinel: modern capture.customer_id tests must not need a live query."""


def _user(role="viewer", customer_id="customer-a"):
    return SimpleNamespace(role=role, customer_id=customer_id, username="tester")


def _capture(customer_id="customer-a", device_id="TL-TEST"):
    return SimpleNamespace(customer_id=customer_id, device_id=device_id)


def test_redaction_mutations_reject_viewer():
    with pytest.raises(HTTPException) as exc:
        _require_role(_user(role="viewer"), "operator")
    assert exc.value.status_code == 403


def test_redaction_mutations_allow_operator_and_above():
    _require_role(_user(role="operator"), "operator")
    _require_role(_user(role="admin"), "operator")
    _require_role(_user(role="super_admin"), "operator")


def test_capture_access_rejects_cross_tenant_principal():
    with pytest.raises(HTTPException) as exc:
        _ensure_capture_access(_NoFallbackDb(), _user(customer_id="customer-a"), _capture(customer_id="customer-b"))
    assert exc.value.status_code == 403


def test_capture_access_allows_matching_frozen_tenant():
    _ensure_capture_access(_NoFallbackDb(), _user(customer_id="customer-a"), _capture(customer_id="customer-a"))


def test_super_admin_may_cross_tenant():
    _ensure_capture_access(_NoFallbackDb(), _user(role="super_admin", customer_id=None), _capture(customer_id="customer-b"))


def test_unknown_role_fails_closed():
    with pytest.raises(HTTPException) as exc:
        _require_role(_user(role="unexpected"), "viewer")
    assert exc.value.status_code == 403


def test_redaction_source_does_not_emit_fake_approval_success():
    import inspect
    import headend.redaction_api as module

    source = inspect.getsource(module.approve_capture)
    assert "status_code=501" in source
    assert '"success": True' not in source


def test_auto_approve_does_not_change_redaction_state_to_approved():
    import inspect
    import headend.redaction_api as module

    source = inspect.getsource(module.redact_capture)
    assert '"redacted"' in source
    assert '"approved"' not in source


def test_false_positive_review_payload_is_explicit_training_evidence():
    capture = SimpleNamespace(
        gdpr_detections={"faces": [{"x": 1, "y": 2, "w": 3, "h": 4}], "has_pii": True},
        redaction_status="detected",
    )

    payload = _false_positive_review_payload(capture, _user(role="operator"))

    assert payload["faces"][0]["x"] == 1
    assert payload["review"]["decision"] == "false_positive"
    assert payload["review"]["previous_status"] == "detected"
    assert payload["review"]["reviewed_by"] == "tester"


def test_false_positive_endpoint_requires_detected_status():
    import inspect
    import headend.redaction_api as module

    source = inspect.getsource(module.mark_false_positive)
    assert 'capture.redaction_status != "detected"' in source
    assert 'capture.redaction_status = "skipped"' in source
    assert 'capture.has_gdpr_data = False' in source
    assert 'capture.redaction_method = "false_positive_review"' in source
