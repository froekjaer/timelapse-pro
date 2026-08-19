"""Unit tests for headend/edge_sync.py — the consolidated Edge<->Headend poll
introduced 2026-08-19 to replace three independently-timed loops (config-pull,
heartbeat, SIEM-forward) plus a redundant nested update-check timer with one
request/response per cycle. See Dokumentation/HANDOVER_LOG.md 2026-08-19.

These verify edge_sync() COMPOSES the existing, already-tested handlers
(heartbeat, get_config, get_update_policy, siem.ingest_events,
cmdb.report_inventory) rather than reimplementing their logic — each is
mocked and asserted to be called with the right arguments, and the response
assembled from their (mocked) return values.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import main
import edge_sync
from edge_sync import EdgeSyncRequest, edge_sync as edge_sync_endpoint


@pytest.mark.asyncio
async def test_edge_sync_composes_heartbeat_config_and_update_policy():
    req = EdgeSyncRequest(
        timestamp="2026-08-19T12:00:00Z",
        diagnostics={"cpu_temperature": 42.0},
        capture_stats={},
        siem_events=[],
        inventory=None,
    )
    db = MagicMock()

    fake_heartbeat = MagicMock(return_value={"server_time": "2026-08-19T12:00:01Z", "config_version": "abc123"})
    fake_config = {"config_version": "abc123", "device": {}}
    fake_get_config = MagicMock(return_value=fake_config)
    fake_policy = {"pending_updates": [{"id": 1}], "app_security": "auto", "app_updates": "manual"}
    fake_get_update_policy = MagicMock(return_value=fake_policy)

    with patch.object(main, "heartbeat", fake_heartbeat), \
         patch.object(main, "get_config", fake_get_config), \
         patch.object(main, "get_update_policy", fake_get_update_policy), \
         patch.object(edge_sync, "resolve_authorized_technician_keys", MagicMock(return_value=[])):
        result = await edge_sync_endpoint("TL-TESTDEVICE0001", req, _auth=None, db=db)

    fake_heartbeat.assert_called_once()
    assert fake_heartbeat.call_args.args[0] == "TL-TESTDEVICE0001"
    fake_get_config.assert_called_once_with("TL-TESTDEVICE0001", _auth=None, db=db)
    fake_get_update_policy.assert_called_once_with("TL-TESTDEVICE0001", _auth=None, db=db)
    assert result["config"] == fake_config
    assert result["pending_updates"] == [{"id": 1}]
    assert result["server_time"] == "2026-08-19T12:00:01Z"
    assert result["app_security"] == "auto"
    assert result["app_updates"] == "manual"


@pytest.mark.asyncio
async def test_edge_sync_includes_authorized_technician_keys_for_the_device():
    req = EdgeSyncRequest(timestamp="t", diagnostics={}, capture_stats={}, siem_events=[], inventory=None)
    db = MagicMock()
    fake_device = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = fake_device
    fake_keys = [{"public_key": "ssh-ed25519 AAAA", "identity": "tekniker1:laptop", "field_role": "technician"}]

    with patch.object(main, "heartbeat", MagicMock(return_value={"server_time": "t", "config_version": "v"})), \
         patch.object(main, "get_config", MagicMock(return_value={})), \
         patch.object(main, "get_update_policy", MagicMock(return_value={"pending_updates": []})), \
         patch.object(edge_sync, "resolve_authorized_technician_keys", MagicMock(return_value=fake_keys)) as fake_resolve:
        result = await edge_sync_endpoint("TL-TESTDEVICE0001", req, _auth=None, db=db)

    fake_resolve.assert_called_once_with(db, fake_device)
    assert result["technician_keys"] == fake_keys


@pytest.mark.asyncio
async def test_edge_sync_forwards_siem_events_and_inventory_when_present():
    req = EdgeSyncRequest(
        timestamp="t",
        diagnostics={},
        capture_stats={},
        siem_events=[{"event_type": "log", "severity": "warning"}],
        inventory={"os_name": "ubuntu"},
    )
    db = MagicMock()

    with patch.object(main, "heartbeat", MagicMock(return_value={"server_time": "t", "config_version": "v"})), \
         patch.object(main, "get_config", MagicMock(return_value={})), \
         patch.object(main, "get_update_policy", MagicMock(return_value={"pending_updates": []})), \
         patch.object(edge_sync, "_siem_ingest_events", new=AsyncMock()) as fake_ingest, \
         patch.object(edge_sync, "_cmdb_report_inventory", MagicMock()) as fake_inventory, \
         patch.object(edge_sync, "resolve_authorized_technician_keys", MagicMock(return_value=[])):
        await edge_sync_endpoint("TL-TESTDEVICE0001", req, _auth=None, db=db)

    fake_ingest.assert_called_once_with(
        "TL-TESTDEVICE0001",
        {"events": [{"event_type": "log", "severity": "warning"}]},
        _auth=None,
        db=db,
    )
    fake_inventory.assert_called_once_with(device_id="TL-TESTDEVICE0001", payload={"os_name": "ubuntu"}, db=db)


@pytest.mark.asyncio
async def test_edge_sync_skips_siem_and_inventory_when_absent():
    req = EdgeSyncRequest(timestamp="t", diagnostics={}, capture_stats={}, siem_events=[], inventory=None)
    db = MagicMock()

    with patch.object(main, "heartbeat", MagicMock(return_value={"server_time": "t", "config_version": "v"})), \
         patch.object(main, "get_config", MagicMock(return_value={})), \
         patch.object(main, "get_update_policy", MagicMock(return_value={"pending_updates": []})), \
         patch.object(edge_sync, "_siem_ingest_events", new=AsyncMock()) as fake_ingest, \
         patch.object(edge_sync, "_cmdb_report_inventory", MagicMock()) as fake_inventory, \
         patch.object(edge_sync, "resolve_authorized_technician_keys", MagicMock(return_value=[])):
        await edge_sync_endpoint("TL-TESTDEVICE0001", req, _auth=None, db=db)

    fake_ingest.assert_not_called()
    fake_inventory.assert_not_called()
