from datetime import datetime, timedelta, timezone

from headend.services.os_inventory_freshness import stale_os_inventory_reason


def test_recent_inventory_is_eligible(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_OS_CATALOG_MAX_INVENTORY_AGE_HOURS", "72")
    assert stale_os_inventory_reason(datetime.now(timezone.utc) - timedelta(hours=71)) is None


def test_old_or_missing_inventory_is_rejected(monkeypatch):
    monkeypatch.setenv("TIMELAPSE_OS_CATALOG_MAX_INVENTORY_AGE_HOURS", "72")
    assert "mangler" in stale_os_inventory_reason(None)
    result = stale_os_inventory_reason(datetime.now(timezone.utc) - timedelta(hours=73))
    assert result and "for gammel" in result
