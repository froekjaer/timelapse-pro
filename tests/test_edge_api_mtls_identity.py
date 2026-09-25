from types import SimpleNamespace

import pytest

from headend.services.edge_api_mtls_identity import (
    EdgeApiMtlsIdentityError,
    canonical_certificate_serial,
    enforcement_mode,
    verify_edge_api_mtls_identity,
)


DEVICE = "TL-C87FF9587CA0"
SERIAL = "00:0A:BC"
CREDENTIAL_ID = "headend-api-mtls:abc"


class FakeQuery:
    def __init__(self, row):
        self.row = row
        self.filters = None

    def filter_by(self, **kwargs):
        self.filters = kwargs
        return self

    def first(self):
        if self.row is None:
            return None
        if self.filters.get("credential_id") != getattr(self.row, "credential_id"):
            return None
        if self.filters.get("device_id") != getattr(self.row, "device_id"):
            return None
        if self.filters.get("status") != getattr(self.row, "status"):
            return None
        return self.row


class FakeDb:
    def __init__(self, row=None):
        self.row = row
        self.query_obj = None

    def query(self, _model):
        self.query_obj = FakeQuery(self.row)
        return self.query_obj


def active_row(device_id=DEVICE, status="active"):
    return SimpleNamespace(
        device_id=device_id,
        credential_id=CREDENTIAL_ID,
        status=status,
    )


def test_enforcement_mode_fails_closed_on_invalid_configuration():
    with pytest.raises(EdgeApiMtlsIdentityError, match="invalid"):
        enforcement_mode("surprise")


def test_certificate_serial_is_canonicalized_like_enrollment():
    assert canonical_certificate_serial(SERIAL) == "abc"


def test_optional_mode_allows_absence_during_migration():
    result = verify_edge_api_mtls_identity(
        FakeDb(),
        device_id=DEVICE,
        headers={},
        mode="optional",
    )
    assert result.presented is False
    assert result.verified is False


def test_required_mode_rejects_absence():
    with pytest.raises(EdgeApiMtlsIdentityError, match="required"):
        verify_edge_api_mtls_identity(
            FakeDb(),
            device_id=DEVICE,
            headers={},
            mode="required",
        )


def test_required_mode_allows_only_explicit_enrollment_recovery_absence():
    result = verify_edge_api_mtls_identity(
        FakeDb(),
        device_id=DEVICE,
        headers={},
        mode="required",
        allow_legacy_enrollment=True,
    )
    assert result.presented is False
    assert result.verified is False


def test_optional_mode_does_not_downgrade_present_invalid_certificate():
    with pytest.raises(EdgeApiMtlsIdentityError, match="not verified"):
        verify_edge_api_mtls_identity(
            FakeDb(),
            device_id=DEVICE,
            headers={"x-tlp-mtls-verify": "FAILED", "x-tlp-mtls-serial": "abc"},
            mode="optional",
        )


def test_verified_certificate_must_be_active_for_exact_device():
    with pytest.raises(EdgeApiMtlsIdentityError, match="not active"):
        verify_edge_api_mtls_identity(
            FakeDb(active_row(device_id="TL-OTHER")),
            device_id=DEVICE,
            headers={"x-tlp-mtls-verify": "SUCCESS", "x-tlp-mtls-serial": SERIAL},
            mode="required",
        )


def test_verified_active_certificate_binds_to_device_inventory():
    db = FakeDb(active_row())
    result = verify_edge_api_mtls_identity(
        db,
        device_id=DEVICE,
        headers={"x-tlp-mtls-verify": "SUCCESS", "x-tlp-mtls-serial": SERIAL},
        mode="required",
    )

    assert result.presented is True
    assert result.verified is True
    assert result.credential_id == CREDENTIAL_ID
    assert db.query_obj.filters["device_id"] == DEVICE
    assert db.query_obj.filters["trust_path"] == "headend_api_mtls"
    assert db.query_obj.filters["key_type"] == "mtls_device_cert"
    assert db.query_obj.filters["status"] == "active"
