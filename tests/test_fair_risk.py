from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "headend"))

from services.fair_risk import estimate_annual_loss, validate_profile  # noqa: E402


PROFILE = {
    "threat_event_frequency_per_year": [1, 2, 4],
    "vulnerability_probability": [0.1, 0.25, 0.5],
    "primary_loss_dkk": [10_000, 50_000, 100_000],
    "secondary_loss_dkk": [0, 10_000, 50_000],
}


def test_fair_estimate_is_reproducible_and_ordered():
    first = estimate_annual_loss(PROFILE, "TL-TEST", samples=2_000)
    second = estimate_annual_loss(PROFILE, "TL-TEST", samples=2_000)
    assert first == second
    assert first["status"] == "estimated"
    assert first["annual_loss"]["p10"] <= first["annual_loss"]["p50"] <= first["annual_loss"]["p90"]


def test_fair_estimate_fails_openly_when_business_inputs_are_missing():
    result = estimate_annual_loss(None, "TL-TEST")
    assert result["status"] == "needs_input"
    assert "primary_loss_dkk" in result["missing"]
    assert "annual_loss" not in result


def test_fair_profile_rejects_invalid_probability():
    invalid = {**PROFILE, "vulnerability_probability": [0.1, 0.5, 1.2]}
    try:
        validate_profile(invalid)
    except ValueError as exc:
        assert "højst" in str(exc)
    else:
        raise AssertionError("invalid FAIR probability accepted")
