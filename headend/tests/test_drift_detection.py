"""
Tests for headend/ai/drift_detection.py (drift-detection fase 1, 2026-07-07).

Dækker: selv-kalibrerende trend-sammenligning (baseline vs. recent vindue) for
de tre dimensioner (focus/exposure/white_balance), config-hierarki-overstyring
(quality.drift_detection.<dimension>.*), sparse-data-tolerance for
white_balance (kun udfyldt når Edge's optimizer kørte), og default-off for
white_balance.

Ingen live Postgres nødvendig — bruger samme mønster som
test_access_ticket_and_device_cert_schema.py (midlertidig SQLite-database).

Kør (fra headend/):
    ~/.venvs/timelapse-headend/bin/python -m pytest tests/test_drift_detection.py -v
"""
import os
import sys
import tempfile
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")

import database  # noqa: E402
from ai.drift_detection import analyse_camera_drift, _trend_shift, _resolve_drift_config  # noqa: E402


@pytest.fixture()
def db_session():
    database.create_tables()
    session = database.SessionLocal()
    try:
        yield session
    finally:
        for table in reversed(database.Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
CAMERA = "cam-drift-test-1"


def _make_capture(db, *, days_ago: float, blur=None, brightness=None, wb=None, idx=0):
    cap = database.Capture(
        device_id="TL-DRIFTTEST",
        filename=f"img_{idx:04d}.jpg",
        captured_at=NOW - timedelta(days=days_ago),
        camera_id=CAMERA,
        blur_score=blur,
        brightness_mean=brightness,
        wb_cast_strength=wb,
    )
    db.add(cap)
    return cap


def _seed(db, *, baseline_n, recent_n, baseline_blur, recent_blur,
          baseline_bright=128.0, recent_bright=128.0,
          baseline_wb=None, recent_wb=None):
    """Seed baseline-vinduet (dag 10-30 siden) og recent-vinduet (dag 0-6
    siden), matcher DEFAULT_DIMENSION_CONFIG's window_days=7/baseline_days=30
    (baseline-perioden er window_days..window_days+baseline_days siden)."""
    idx = 0
    for i in range(baseline_n):
        days_ago = 10 + (i % 20)  # spredt over baseline-vinduet
        _make_capture(
            db, days_ago=days_ago,
            blur=baseline_blur + (i % 3 - 1) * 2,  # lille, deterministisk spredning
            brightness=baseline_bright + (i % 3 - 1),
            wb=baseline_wb,
            idx=idx,
        )
        idx += 1
    for i in range(recent_n):
        days_ago = i % 6
        _make_capture(
            db, days_ago=days_ago,
            blur=recent_blur + (i % 3 - 1) * 2,
            brightness=recent_bright + (i % 3 - 1),
            wb=recent_wb,
            idx=idx,
        )
        idx += 1
    db.commit()


# ── _trend_shift (ren funktion, ingen DB) ───────────────────────────────────

def test_trend_shift_detects_lower_direction_drift():
    baseline = [500.0, 510.0, 495.0, 505.0, 502.0]
    recent = [200.0, 210.0, 195.0, 205.0, 202.0]
    result = _trend_shift(baseline, recent, worse_direction="lower", z_threshold=2.0, min_samples=5)
    assert result["sufficient_data"] is True
    assert result["drift_suspected"] is True
    assert result["z_score"] < -2.0


def test_trend_shift_no_drift_for_similar_windows():
    baseline = [500.0, 510.0, 495.0, 505.0, 502.0]
    recent = [498.0, 508.0, 501.0, 503.0, 499.0]
    result = _trend_shift(baseline, recent, worse_direction="lower", z_threshold=2.0, min_samples=5)
    assert result["drift_suspected"] is False


def test_trend_shift_higher_direction_only_flags_increase():
    baseline = [0.02, 0.03, 0.025, 0.02, 0.022]
    recent = [0.02, 0.021, 0.019, 0.02, 0.018]  # faldet, IKKE steget
    result = _trend_shift(baseline, recent, worse_direction="higher", z_threshold=2.0, min_samples=5)
    assert result["drift_suspected"] is False, "fald skal ikke flages naar 'higher' er den vaerre retning"

    recent_worse = [0.09, 0.10, 0.095, 0.11, 0.10]
    result_worse = _trend_shift(baseline, recent_worse, worse_direction="higher", z_threshold=2.0, min_samples=5)
    assert result_worse["drift_suspected"] is True


def test_trend_shift_either_direction_flags_both_ways():
    baseline = [128.0, 130.0, 126.0, 129.0, 127.0]
    darker = [90.0, 88.0, 92.0, 89.0, 91.0]
    brighter = [170.0, 172.0, 168.0, 171.0, 169.0]
    assert _trend_shift(baseline, darker, worse_direction="either", z_threshold=2.0, min_samples=5)["drift_suspected"] is True
    assert _trend_shift(baseline, brighter, worse_direction="either", z_threshold=2.0, min_samples=5)["drift_suspected"] is True


def test_trend_shift_insufficient_data():
    result = _trend_shift([1.0, 2.0], [1.0, 2.0], worse_direction="lower", z_threshold=2.0, min_samples=5)
    assert result["sufficient_data"] is False
    assert result["baseline_n"] == 2
    assert result["recent_n"] == 2


def test_trend_shift_handles_zero_baseline_variance_without_crashing():
    baseline = [500.0, 500.0, 500.0, 500.0, 500.0]
    recent = [499.0, 500.0, 501.0, 500.0, 499.0]
    result = _trend_shift(baseline, recent, worse_direction="lower", z_threshold=2.0, min_samples=5)
    assert result["sufficient_data"] is True
    assert result["drift_suspected"] is False  # for lille aendring til at flage, selv med floor_stdev


# ── _resolve_drift_config (hierarki-merge) ──────────────────────────────────

def test_resolve_drift_config_uses_defaults_when_no_overrides():
    resolved = _resolve_drift_config(None)
    assert resolved["focus"]["enabled"] is True
    assert resolved["exposure"]["enabled"] is True
    assert resolved["white_balance"]["enabled"] is False  # default-off


def test_resolve_drift_config_partial_override_keeps_other_defaults():
    raw = {"quality": {"drift_detection": {"focus": {"z_threshold": 3.5}}}}
    resolved = _resolve_drift_config(raw)
    assert resolved["focus"]["z_threshold"] == 3.5
    assert resolved["focus"]["window_days"] == 7  # uroert default
    assert resolved["exposure"]["z_threshold"] == 2.5  # uroert dimension


def test_resolve_drift_config_can_enable_white_balance():
    raw = {"quality": {"drift_detection": {"white_balance": {"enabled": True}}}}
    resolved = _resolve_drift_config(raw)
    assert resolved["white_balance"]["enabled"] is True


# ── analyse_camera_drift (DB-integration) ───────────────────────────────────

def test_analyse_camera_drift_flags_focus_drift(db_session):
    _seed(db_session, baseline_n=8, recent_n=8, baseline_blur=550.0, recent_blur=150.0)
    result = analyse_camera_drift(db_session, database.Capture, CAMERA, raw_config=None, now=NOW)
    assert result["focus"]["drift_suspected"] is True
    assert result["focus"]["sufficient_data"] is True
    assert result["exposure"]["drift_suspected"] is False  # lys uaendret i seed


def test_analyse_camera_drift_no_drift_when_stable(db_session):
    _seed(db_session, baseline_n=8, recent_n=8, baseline_blur=500.0, recent_blur=505.0)
    result = analyse_camera_drift(db_session, database.Capture, CAMERA, raw_config=None, now=NOW)
    assert result["focus"]["drift_suspected"] is False


def test_analyse_camera_drift_white_balance_disabled_by_default(db_session):
    _seed(db_session, baseline_n=8, recent_n=8, baseline_blur=500.0, recent_blur=500.0,
          baseline_wb=0.02, recent_wb=0.20)  # kraftig aendring - men skal ignoreres naar slaaet fra
    result = analyse_camera_drift(db_session, database.Capture, CAMERA, raw_config=None, now=NOW)
    assert result["white_balance"]["enabled"] is False
    assert result["white_balance"]["drift_suspected"] is False
    assert result["white_balance"]["sufficient_data"] is False


def test_analyse_camera_drift_white_balance_detects_when_enabled(db_session):
    _seed(db_session, baseline_n=8, recent_n=8, baseline_blur=500.0, recent_blur=500.0,
          baseline_wb=0.02, recent_wb=0.20)
    raw = {"quality": {"drift_detection": {"white_balance": {"enabled": True}}}}
    result = analyse_camera_drift(db_session, database.Capture, CAMERA, raw_config=raw, now=NOW)
    assert result["white_balance"]["enabled"] is True
    assert result["white_balance"]["drift_suspected"] is True


def test_analyse_camera_drift_tolerates_sparse_white_balance(db_session):
    """wb_cast_strength er kun udfyldt naar Edge's optimizer koerte - de
    fleste rækker skal kunne have NULL uden at braekke analysen, saa laenge
    der er nok IKKE-NULL vaerdier i hvert vindue."""
    _seed(db_session, baseline_n=20, recent_n=20, baseline_blur=500.0, recent_blur=500.0,
          baseline_wb=None, recent_wb=None)
    # Tilfoej et lille antal rækker MED wb-data i begge vinduer (>= min_samples=5)
    for i, days_ago in enumerate([25, 22, 18, 15, 12]):
        _make_capture(db_session, days_ago=days_ago, blur=500.0, brightness=128.0, wb=0.02, idx=1000 + i)
    for i, days_ago in enumerate([5, 4, 3, 2, 1]):
        _make_capture(db_session, days_ago=days_ago, blur=500.0, brightness=128.0, wb=0.25, idx=2000 + i)
    db_session.commit()

    raw = {"quality": {"drift_detection": {"white_balance": {"enabled": True, "min_samples": 5}}}}
    result = analyse_camera_drift(db_session, database.Capture, CAMERA, raw_config=raw, now=NOW)
    assert result["white_balance"]["sufficient_data"] is True
    assert result["white_balance"]["baseline_n"] == 5
    assert result["white_balance"]["recent_n"] == 5
    assert result["white_balance"]["drift_suspected"] is True


def test_analyse_camera_drift_insufficient_data_for_new_camera(db_session):
    _make_capture(db_session, days_ago=1, blur=500.0, brightness=128.0, idx=1)
    db_session.commit()
    result = analyse_camera_drift(db_session, database.Capture, CAMERA, raw_config=None, now=NOW)
    assert result["focus"]["sufficient_data"] is False
    assert result["focus"]["drift_suspected"] is False


def test_analyse_camera_drift_ignores_other_cameras(db_session):
    _seed(db_session, baseline_n=8, recent_n=8, baseline_blur=550.0, recent_blur=150.0)
    # Et andet kamera med DRAMATISK drift, som IKKE maa smitte af paa CAMERA's resultat
    other = "cam-other"
    for i in range(8):
        cap = database.Capture(
            device_id="TL-OTHER", filename=f"other_{i}.jpg",
            captured_at=NOW - timedelta(days=15), camera_id=other,
            blur_score=900.0, brightness_mean=128.0,
        )
        db_session.add(cap)
    db_session.commit()

    result = analyse_camera_drift(db_session, database.Capture, CAMERA, raw_config=None, now=NOW)
    assert result["focus"]["drift_suspected"] is True  # egen data, uaendret af det andet kamera
