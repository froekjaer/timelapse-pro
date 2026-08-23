"""Regression test for a real production bug found live 2026-08-23: the
config_defaults table is meant to hold exactly one row (the global config
baseline for schedule/camera/quality/storage/diagnostics/system/session_policy),
but a check-then-insert race in _get_or_create_defaults() let a second row get
created. With no explicit ordering, `db.query(ConfigDefaults).first()` is not
guaranteed to return the same row from every call site — confirmed empirically:
get_config() (used by SystemAdminPage's per-device view) and get_config_defaults()
(used by GlobalConfigPage) resolved DIFFERENT rows, so an admin's edit on one
page silently didn't show up on the other. Every one of the four call sites now
orders by id ascending, so the same (lowest-id) row always wins everywhere,
regardless of how many duplicate rows exist.
"""
from database import Base, ConfigDefaults, SessionLocal, engine

import main


def _reset_config_defaults_table():
    with engine.connect() as conn:
        conn.execute(ConfigDefaults.__table__.delete())
        conn.commit()


def test_get_or_create_defaults_is_deterministic_with_duplicate_rows():
    _reset_config_defaults_table()
    db = SessionLocal()
    try:
        first = ConfigDefaults(
            schedule='{"interval_minutes": 60}', camera="{}", quality="{}",
            storage="{}", diagnostics='{"sync_poll_interval_minutes": 1}',
            system="{}", session_policy="{}",
        )
        second = ConfigDefaults(
            schedule='{"interval_minutes": 10}', camera="{}", quality="{}",
            storage="{}", diagnostics='{"sync_poll_interval_minutes": 5}',
            system="{}", session_policy="{}",
        )
        db.add(first); db.add(second); db.commit()
        db.refresh(first); db.refresh(second)
        assert first.id < second.id

        # Every call site must resolve to the SAME (lowest-id) row.
        resolved = main._get_or_create_defaults(db)
        assert resolved.id == first.id

        # Repeated calls, including from a fresh session, must agree —
        # this is what was actually broken: two different code paths
        # disagreeing on which row is "the" config.
        db2 = SessionLocal()
        try:
            resolved2 = main._get_or_create_defaults(db2)
            assert resolved2.id == first.id
        finally:
            db2.close()
    finally:
        db.close()
        _reset_config_defaults_table()


def test_get_config_defaults_and_update_config_defaults_agree_with_duplicate_rows():
    _reset_config_defaults_table()
    db = SessionLocal()
    try:
        winner = ConfigDefaults(
            schedule="{}", camera="{}", quality="{}", storage="{}",
            diagnostics='{"sync_poll_interval_minutes": 1}',
            system="{}", session_policy="{}",
        )
        loser = ConfigDefaults(
            schedule="{}", camera="{}", quality="{}", storage="{}",
            diagnostics='{"sync_poll_interval_minutes": 5}',
            system="{}", session_policy="{}",
        )
        db.add(winner); db.add(loser); db.commit()

        via_get = main.get_config_defaults(_user=None, db=db)
        assert via_get["diagnostics"]["sync_poll_interval_minutes"] == 1

        main.update_config_defaults({"diagnostics": {"sync_poll_interval_minutes": 7}}, _user=None, db=db)
        db.expire_all()

        via_get_after = main.get_config_defaults(_user=None, db=db)
        assert via_get_after["diagnostics"]["sync_poll_interval_minutes"] == 7

        # The other (higher-id) row must be untouched — proves the update
        # landed on the same canonical row get_config_defaults() reads.
        untouched = db.query(ConfigDefaults).filter_by(id=loser.id).first()
        import json
        assert json.loads(untouched.diagnostics)["sync_poll_interval_minutes"] == 5
    finally:
        db.close()
        _reset_config_defaults_table()


def test_get_config_priority_chain_factory_lt_global_lt_device():
    """The actual production bug: Lag 1 (config_defaults / "Global Config" in
    the admin UI) used to be merged as _deep_merge(d, cfg[section]) — since
    _deep_merge(base, override) has override win, the hardcoded factory
    literal cfg was already built with (plus, until the reorder, an
    already-applied device_config override on top of it) outranked the
    admin's actual Global Config edit. Confirmed live against a real device
    2026-08-23: Global Config set sync_poll_interval_minutes=1, but
    get_config() kept returning the hardcoded factory value of 5.

    This proves the full intended priority chain for one section
    (diagnostics) end to end: factory hardcoded < Global Config <
    per-device device_config override.
    """
    from database import Device

    _reset_config_defaults_table()
    db = SessionLocal()
    try:
        device_id = "TL-TEST-CONFIG-PRIORITY"
        db.query(Device).filter_by(device_id=device_id).delete()
        db.commit()

        # Global Config sets sync_poll=1 (must beat the factory default of 5)
        # but does NOT set update_poll_interval_minutes (factory default of
        # 5 must survive for that key, since nothing overrides it).
        defaults = ConfigDefaults(
            schedule="{}", camera="{}", quality="{}", storage="{}",
            diagnostics='{"sync_poll_interval_minutes": 1}',
            system="{}", session_policy="{}",
        )
        db.add(defaults)

        # This device has its OWN override for update_poll (must beat both
        # the factory default AND Global Config).
        device = Device(
            device_id=device_id,
            device_config='{"diagnostics": {"update_poll_interval_minutes": 42}}',
        )
        db.add(device)
        db.commit()

        cfg = main.get_config(device_id, _auth=None, db=db)
        diag = cfg["diagnostics"]
        assert diag["sync_poll_interval_minutes"] == 1, "Global Config must beat the factory default"
        assert diag["update_poll_interval_minutes"] == 42, "Device-specific override must beat Global Config"
        assert diag["inventory_report_interval_hours"] == 24, "Untouched factory default must still come through"
    finally:
        from database import Device as _Device
        db.query(_Device).filter_by(device_id="TL-TEST-CONFIG-PRIORITY").delete()
        db.commit()
        db.close()
        _reset_config_defaults_table()
