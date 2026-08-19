"""Regression tests for the BT-TOTP resolution helper and the admin
"local access" overview endpoint (headend/local_access.py), built 2026-08-19
per Peter: "alle enheder der er konfigureret en TOTP kode til [skal være]
tilgængelige, og kan ses (jfr. RBAC)."

_resolve_camera_bt_totp() was extracted from get_camera_bt_totp_qr() so both
the single-camera QR endpoint and this list endpoint share one resolution
implementation — these tests exercise the extracted function directly.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import main
import local_access


def _fake_camera(**overrides):
    defaults = dict(id="cam-1", site_id=None, customer_id=None, bt_totp_secret=None, bt_totp_sid=None, camera_name="Test-kamera")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _db_with(site=None, customer=None):
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if name == "Site":
            q.filter_by.return_value.first.return_value = site
        elif name == "Customer":
            q.filter_by.return_value.first.return_value = customer
        else:
            q.filter_by.return_value.first.return_value = None
        return q

    db.query.side_effect = query_side_effect
    return db


def test_resolve_camera_bt_totp_prefers_camera_over_all_other_layers():
    cam = _fake_camera(bt_totp_secret="CAMSECRET", bt_totp_sid="cam-sid")
    db = _db_with()
    with patch.object(main, "_get_setting", return_value="GLOBALSECRET"):
        secret, sid, source = main._resolve_camera_bt_totp(db, cam)
    assert (secret, sid, source) == ("CAMSECRET", "cam-sid", "kamera")


def test_resolve_camera_bt_totp_falls_back_to_site_then_global():
    cam = _fake_camera(site_id="site-1")
    site = SimpleNamespace(id="site-1", customer_id="cust-1", config_overrides='{"bt_totp": {"secret": "SITESECRET", "sid": "site-sid"}}')
    db = _db_with(site=site)
    with patch.object(main, "_get_setting", side_effect=lambda db, key, default: {"bt_totp_secret": "GLOBALSECRET", "bt_totp_sid": "global-sid"}.get(key, default)):
        secret, sid, source = main._resolve_camera_bt_totp(db, cam)
    assert (secret, sid, source) == ("SITESECRET", "site-sid", "site")


def test_resolve_camera_bt_totp_returns_empty_when_no_layer_configured():
    cam = _fake_camera()
    db = _db_with()
    with patch.object(main, "_get_setting", return_value=""):
        secret, sid, source = main._resolve_camera_bt_totp(db, cam)
    assert (secret, sid, source) == ("", "", "")


def test_list_local_access_never_returns_secret_or_qr_fields():
    cam = _fake_camera(camera_name="Mod baggård")
    db = MagicMock()
    with patch.object(main, "_visible_camera_query") as fake_query, \
         patch.object(main, "_resolve_camera_bt_totp", return_value=("s3cr3t", "sid-1", "kamera")):
        fake_query.return_value.order_by.return_value.all.return_value = [cam]
        db.query.return_value.filter_by.return_value.first.return_value = None
        rows = local_access.list_local_access(current_user=MagicMock(), db=db)

    assert len(rows) == 1
    row = rows[0]
    assert row["camera_name"] == "Mod baggård"
    assert row["sid"] == "sid-1"
    assert row["source"] == "kamera"
    assert "secret" not in row
    assert "qr_code" not in row
    assert "current_code" not in row


def test_list_local_access_marks_unprovisioned_cameras():
    cam = _fake_camera(camera_name="Ny kamera uden adgang")
    db = MagicMock()
    with patch.object(main, "_visible_camera_query") as fake_query, \
         patch.object(main, "_resolve_camera_bt_totp", return_value=("", "", "")):
        fake_query.return_value.order_by.return_value.all.return_value = [cam]
        db.query.return_value.filter_by.return_value.first.return_value = None
        rows = local_access.list_local_access(current_user=MagicMock(), db=db)

    assert rows[0]["source"] == "unprovisioned"
    assert rows[0]["sid"] is None
