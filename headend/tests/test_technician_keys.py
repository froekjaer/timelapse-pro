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
