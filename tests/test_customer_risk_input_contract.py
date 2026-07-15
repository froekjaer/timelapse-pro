from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text()


def test_customer_price_is_versioned_not_stored_as_unstructured_override():
    database = source("headend/database.py")
    assert "class CustomerRiskInput" in database
    assert "monthly_service_price" in database
    assert "effective_from" in database and "effective_to" in database
    assert "validated_by" in database and "validated_at" in database


def test_customer_price_api_is_platform_admin_and_mfa_protected():
    api = source("headend/api/customer_risk_api.py")
    assert "def _require_platform_admin" in api
    assert "_is_platform_admin(user)" in api
    assert "_mfa_required_for_user" in api
    assert "with_for_update()" in api


def test_database_enforces_one_open_version_and_positive_price():
    migration = source("headend/migrations/v20_customer_risk_inputs.sql")
    assert "monthly_service_price > 0" in migration
    assert "WHERE effective_to IS NULL" in migration
    assert "UNIQUE INDEX" in migration


def test_monthly_price_is_only_readiness_input_not_automatic_fair_loss():
    cmdb = source("headend/cmdb.py")
    assert 'fair["monthly_service_price_available"]' in cmdb
    assert "estimate_annual_loss(None, device_id)" in cmdb


def test_customer_risk_profile_is_versioned_and_requires_validation():
    database = source("headend/database.py")
    api = source("headend/api/customer_risk_api.py")
    assert "class CustomerRiskProfile" in database
    assert 'status="submitted"' in api
    assert "decision not in" in api
    assert 'CustomerRiskProfile.status == "validated"' in api
    assert "superseded" in api
