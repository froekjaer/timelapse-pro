"""Small, auditable FAIR-style annual loss model for operational assets."""

from __future__ import annotations

import hashlib
import random
from typing import Any


TRIPLET_FIELDS = (
    "threat_event_frequency_per_year",
    "vulnerability_probability",
    "primary_loss_dkk",
    "secondary_loss_dkk",
)


def validate_profile(profile: dict[str, Any]) -> dict[str, list[float]]:
    clean: dict[str, list[float]] = {}
    for field in TRIPLET_FIELDS:
        value = profile.get(field)
        if not isinstance(value, list) or len(value) != 3:
            raise ValueError(f"{field} skal være [min, mest_sandsynlig, max]")
        triplet = [float(item) for item in value]
        if triplet[0] < 0 or not triplet[0] <= triplet[1] <= triplet[2]:
            raise ValueError(f"{field} skal være stigende og ikke-negativ")
        if field == "vulnerability_probability" and triplet[2] > 1:
            raise ValueError("vulnerability_probability må højst være 1")
        clean[field] = triplet
    return clean


def estimate_annual_loss(profile: dict[str, Any] | None, seed_key: str, samples: int = 10_000) -> dict[str, Any]:
    if not profile:
        return {"status": "needs_input", "missing": list(TRIPLET_FIELDS), "currency": "DKK"}
    missing = [field for field in TRIPLET_FIELDS if field not in profile]
    if missing:
        return {"status": "needs_input", "missing": missing, "currency": "DKK"}

    clean = validate_profile(profile)
    seed = int(hashlib.sha256(seed_key.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    losses: list[float] = []
    for _ in range(samples):
        tef = rng.triangular(*clean["threat_event_frequency_per_year"])
        vulnerability = rng.triangular(*clean["vulnerability_probability"])
        primary = rng.triangular(*clean["primary_loss_dkk"])
        secondary = rng.triangular(*clean["secondary_loss_dkk"])
        losses.append(tef * vulnerability * (primary + secondary))
    losses.sort()

    def percentile(p: float) -> int:
        return round(losses[min(len(losses) - 1, int((len(losses) - 1) * p))])

    return {
        "status": "estimated",
        "currency": "DKK",
        "annual_loss": {"p10": percentile(0.10), "p50": percentile(0.50), "p90": percentile(0.90)},
        "samples": samples,
        "method": "FAIR-style Monte Carlo v1",
        "assumptions": clean,
        "limitations": [
            "Input estimates require business-owner validation.",
            "Loss distributions are triangular and factors are treated as independent.",
            "This is decision support, not a guarantee of future loss.",
        ],
    }
