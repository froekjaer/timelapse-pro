"""Regression tests for the break-glass/RBAC redesign's first slice
(2026-08-19, per Peter): field-role SSH key management and RBAC-scoped
replication to edge devices.

_has_field_access() and FIELD_ROLES replace the old on_site_service boolean.
resolve_authorized_technician_keys() is what headend/edge_sync.py includes
in every consolidated sync-poll response; edge/agent.py caches it locally
for sshd's AuthorizedKeysCommand to read offline.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import main
import technician_keys


def _fake_user(**overrides):
    defaults = dict(id=1, username="tekniker1", role="operator", customer_id=None, field_role="none", is_active=True)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_has_field_access_true_only_for_installer_or_technician():
    assert main._has_field_access(_fake_user(field_role="installer")) is True
    assert main._has_field_access(_fake_user(field_role="technician")) is True
    assert main._has_field_access(_fake_user(field_role="none")) is False
    assert main._has_field_access(None) is False


def test_validate_public_key_accepts_known_prefixes_rejects_others():
    assert technician_keys._validate_public_key("ssh-ed25519 AAAAC3Nz test@laptop") == "ssh-ed25519 AAAAC3Nz test@laptop"
    import fastapi
    for bad in ("not-a-key", "-----BEGIN OPENSSH PRIVATE KEY-----", ""):
        try:
            technician_keys._validate_public_key(bad)
            assert False, f"expected rejection for {bad!r}"
        except fastapi.HTTPException:
            pass


def test_resolve_authorized_technician_keys_includes_global_and_matching_customer():
    device = SimpleNamespace(customer_id="cust-A")
    global_tech = _fake_user(id=1, username="global-tech", customer_id=None, field_role="technician")
    matching_tech = _fake_user(id=2, username="cust-a-tech", customer_id="cust-A", field_role="installer")
    other_customer_tech = _fake_user(id=3, username="cust-b-tech", customer_id="cust-B", field_role="technician")

    db = MagicMock()
    user_q = MagicMock()
    user_q.filter.return_value.filter.return_value.all.return_value = [global_tech, matching_tech, other_customer_tech]

    def query_dispatch(model):
        if model is technician_keys.User:
            return user_q
        if model is technician_keys.UserSSHKey:
            key_q = MagicMock()

            def filter_by(**kw):
                fq = MagicMock()
                uid = kw["user_id"]
                keys = [SimpleNamespace(public_key=f"ssh-ed25519 KEY-{uid}", label="laptop", id=99)] if uid in (1, 2) else []
                fq.filter.return_value.all.return_value = keys
                return fq
            key_q.filter_by.side_effect = filter_by
            return key_q
        raise AssertionError(f"unexpected model {model}")

    db.query.side_effect = query_dispatch

    entries = technician_keys.resolve_authorized_technician_keys(db, device)

    identities = {e["identity"] for e in entries}
    assert "global-tech:laptop" in identities
    assert "cust-a-tech:laptop" in identities
    assert not any("cust-b-tech" in i for i in identities)
    assert len(entries) == 2


def test_drop_orphaned_device_credential_columns_drops_all_four():
    """FIND-DEVICES-PLAINTEXT-SSH-KEY-COLUMN cleanup: must attempt to drop
    every one of the four orphaned columns, independently — one already
    being gone (or the ALTER failing for any reason) must not block the
    others."""
    executed = []
    conn = MagicMock()
    conn.execute.side_effect = lambda stmt: executed.append(str(stmt))
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    engine = MagicMock()
    engine.connect.return_value = conn

    technician_keys.drop_orphaned_device_credential_columns(engine)

    assert any("ssh_private_key" in s for s in executed)
    assert any("bt_totp_secret" in s for s in executed)
    assert any("factory_totp_disabled" in s for s in executed)
    assert any("shared_ssh_key_disabled" in s for s in executed)
    assert all("DROP COLUMN IF EXISTS" in s for s in executed)


def test_drop_orphaned_device_credential_columns_one_failure_does_not_block_others():
    conn = MagicMock()
    calls = {"n": 0}

    def flaky_execute(stmt):
        calls["n"] += 1
        if "ssh_private_key" in str(stmt):
            raise RuntimeError("simulated failure")
        return MagicMock()

    conn.execute.side_effect = flaky_execute
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    engine = MagicMock()
    engine.connect.return_value = conn

    # Must not raise even though one column's DROP fails.
    technician_keys.drop_orphaned_device_credential_columns(engine)
    assert calls["n"] == 4
