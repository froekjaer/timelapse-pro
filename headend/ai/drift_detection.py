"""
TimeLapse Pro — Drift-detection (fase 1)
═══════════════════════════════════════════════════════════════════════════
Formål: opdage at et FYSISK KAMERA glider ud af kalibrering over tid — ikke
"dette ene billede er dårligt" (det håndterer edge/capture/quality.py og
edge/ai/autonomous_optimizer.py allerede, øjebliksbillede for øjebliksbillede)
men "de sidste N dage er systematisk anderledes end de foregående M dage".

Baggrund (Peters ønske, 2026-07-07): manuelt fokus bruges bevidst for at
undgå slid på autofokusmotoren — men det betyder fokus KAN glide over uger/
måneder uden at nogen bemærker det, fordi hvert enkelt billede stadig kan
ligge lige omkring kvalitetsgrænsen. Samme spørgsmål gælder eksponering
(linsen bliver støvet/tåget, sæsonlys ændrer sig) og hvidbalance (linse-
belægning, sensor-drift). Peter bad EKSPLICIT om at de tre dimensioner
designes sammen, ikke kun fokus, så de deler samme mønster og samme til/fra-
kontakt i config-hierakiet (global/kunde/site/kamera — se
_resolve_config_hierarchy i headend/main.py).

Design-principper:
- REN funktion, ingen kameraStyring, intet auto-trigger, intet auto-apply.
  Fase 1 er UDELUKKENDE et bedre alarmsignal. Fase 2 (auto-trigger en
  focus-slice) og fase 3 (auto-anvend bedste fokus) er separate, senere
  skridt — se HANDOVER_LOG.md 2026-07-07 for den fulde faseplan Peter har
  godkendt.
- Kører på HEADEND, ikke Edge — al historik er allerede her, indekseret
  (captures.camera_id + captures.captured_at, se migration v16), og Edge-
  boards er ressourcebegrænsede. Ingen grund til at duplikere logikken der.
- Selv-kalibrerende pr. kamera: i stedet for en fast, global tærskel
  ("blur < 200 er drift") sammenlignes det NYESTE vindue med et ældre
  BASELINE-vindue for SAMME kamera, og afvigelsen måles i antal standard-
  afvigelser af kameraets EGEN historiske variation. Det gør detektoren
  robust mod normal dag-til-dag/sæson-variation (som Peter selv nævnte),
  fordi et kamera der i forvejen har meget spredning naturligt kræver et
  større absolut skift før det flages, og omvendt for et meget stabilt
  kamera.
- Sparse-data-tolerant: white_balance (wb_cast_strength) er kun udfyldt når
  Edge's autonome optimizer kørte (se _extract_wb_cast_strength i
  headend/main.py) — IKKE på hver capture. Detektoren kræver blot
  min_samples gyldige (ikke-NULL) datapunkter i hvert vindue, uanset hvor
  mange captures der reelt ligger i perioden.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_
from sqlalchemy.orm import Session

# database.Capture importeres af kalderen (headend/main.py) for at undgå
# cirkulær import her — se analyse_camera_drift()'s docstring.


DimensionKey = Literal["focus", "exposure", "white_balance"]

# Standard-tærskler pr. dimension — kan overstyres pr. lag i config-
# hierakiet under quality.drift_detection.<dimension>.*. Se
# _resolve_drift_config() nedenfor for hvordan defaults og overrides merges.
DEFAULT_DIMENSION_CONFIG: dict[DimensionKey, dict] = {
    "focus": {
        "enabled": True,
        "window_days": 7,
        "baseline_days": 30,
        "z_threshold": 2.0,
        "min_samples": 5,
    },
    "exposure": {
        "enabled": True,
        "window_days": 7,
        "baseline_days": 30,
        "z_threshold": 2.5,
        "min_samples": 5,
    },
    "white_balance": {
        # Slået FRA som default indtil videre: wb_cast_strength er sparse
        # (kun udfyldt når optimizeren har kørt), så der typisk skal en
        # længere periode til før der er nok datapunkter. Peter/kunder kan
        # slå den til pr. lag når de har nok historik.
        "enabled": False,
        "window_days": 7,
        "baseline_days": 30,
        "z_threshold": 2.0,
        "min_samples": 5,
    },
}

# Hvilken kolonne og hvilken retning der er "værre" for hver dimension.
# exposure har bevidst retning "either" — både lysere og mørkere over tid
# kan indikere et problem (støv/tåge/sæson/kamera-drift), i modsætning til
# fokus og hvidbalance hvor kun ÉN retning er entydigt dårlig.
_DIMENSION_FIELD: dict[DimensionKey, tuple[str, Literal["lower", "higher", "either"]]] = {
    "focus": ("blur_score", "lower"),
    "exposure": ("brightness_mean", "either"),
    "white_balance": ("wb_cast_strength", "higher"),
}


@dataclass
class DriftResult:
    dimension: DimensionKey
    enabled: bool
    sufficient_data: bool
    baseline_n: int = 0
    recent_n: int = 0
    baseline_mean: float | None = None
    baseline_stdev: float | None = None
    recent_mean: float | None = None
    delta: float | None = None
    z_score: float | None = None
    drift_suspected: bool = False
    message: str = ""
    config: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "enabled": self.enabled,
            "sufficient_data": self.sufficient_data,
            "baseline_n": self.baseline_n,
            "recent_n": self.recent_n,
            "baseline_mean": _round_or_none(self.baseline_mean),
            "baseline_stdev": _round_or_none(self.baseline_stdev),
            "recent_mean": _round_or_none(self.recent_mean),
            "delta": _round_or_none(self.delta),
            "z_score": _round_or_none(self.z_score, 2),
            "drift_suspected": self.drift_suspected,
            "message": self.message,
            "config": self.config,
        }


def _round_or_none(value: float | None, ndigits: int = 3) -> float | None:
    return round(value, ndigits) if value is not None else None


def _naive_utc(dt: datetime) -> datetime:
    """Normaliser til naiv UTC. SQLite (tests) og Postgres (produktion) kan
    returnere hhv. naive og tz-aware datetimes for samme kolonnetype — denne
    funktion sikrer at Python-side-sammenligninger altid er mellem to naive
    UTC-værdier, uanset hvilken driver der er i spil. Naive input antages
    allerede at være UTC (samme konvention som database.now_utc() i resten
    af projektet)."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _resolve_drift_config(raw_config: dict | None) -> dict[DimensionKey, dict]:
    """Merge quality.drift_detection.<dimension> fra det resolverede
    hierarki-config (global→kunde→site→kamera, se _resolve_config_hierarchy)
    ind over DEFAULT_DIMENSION_CONFIG. Ukendte/manglende felter falder
    tilbage til default pr. felt, ikke pr. dimension — så man kan overstyre
    fx kun z_threshold pr. kamera uden at skulle gentage window_days osv.
    """
    resolved: dict[DimensionKey, dict] = {
        dim: dict(defaults) for dim, defaults in DEFAULT_DIMENSION_CONFIG.items()
    }
    quality = (raw_config or {}).get("quality", {}) or {}
    overrides = quality.get("drift_detection", {}) or {}
    for dim in resolved:
        dim_override = overrides.get(dim) or {}
        if isinstance(dim_override, dict):
            resolved[dim].update({k: v for k, v in dim_override.items() if v is not None})
    return resolved


def _trend_shift(
    baseline_values: list[float],
    recent_values: list[float],
    *,
    worse_direction: Literal["lower", "higher", "either"],
    z_threshold: float,
    min_samples: int,
) -> dict:
    """Kernelogik: sammenlign to vinduer af tal, returnér om skiftet fra
    baseline til recent er statistisk usædvanligt for DETTE kameras egen
    historiske spredning, og om skiftet går i den "værre" retning.

    z_score er (recent_mean - baseline_mean) / baseline_stdev. Hvis
    baseline_stdev er 0 (kameraet har historisk haft NUL variation — meget
    usandsynligt for reelle billeder, men muligt i tests/syntetisk data),
    falder vi tilbage til en lille gulv-værdi for at undgå division med nul,
    hvilket gør sammenligningen konservativ (kræver et absolut, ikke bare
    relativt, skift) i stedet for at crashe eller producere ±uendelig.
    """
    baseline_n, recent_n = len(baseline_values), len(recent_values)
    if baseline_n < min_samples or recent_n < min_samples:
        return {
            "sufficient_data": False,
            "baseline_n": baseline_n,
            "recent_n": recent_n,
        }

    baseline_mean = statistics.fmean(baseline_values)
    baseline_stdev = statistics.pstdev(baseline_values) if baseline_n > 1 else 0.0
    recent_mean = statistics.fmean(recent_values)
    delta = recent_mean - baseline_mean

    floor_stdev = max(baseline_stdev, abs(baseline_mean) * 0.02, 1e-6)
    z_score = delta / floor_stdev

    if worse_direction == "lower":
        worse = z_score <= -z_threshold
    elif worse_direction == "higher":
        worse = z_score >= z_threshold
    else:
        worse = abs(z_score) >= z_threshold

    return {
        "sufficient_data": True,
        "baseline_n": baseline_n,
        "recent_n": recent_n,
        "baseline_mean": baseline_mean,
        "baseline_stdev": baseline_stdev,
        "recent_mean": recent_mean,
        "delta": delta,
        "z_score": z_score,
        "drift_suspected": worse,
    }


_MESSAGES: dict[DimensionKey, dict[str, str]] = {
    "focus": {
        "drift": "Skarphed (blur_score) er faldet markant de sidste {window_days} dage sammenlignet med de foregående {baseline_days} dage — muligt tegn på at fokus glider (manuelt fokus slider ikke automatisk korrigeret).",
        "ok": "Ingen usædvanlig ændring i skarphed for perioden.",
        "insufficient": "Ikke nok billeder med blur_score i begge vinduer til en pålidelig sammenligning endnu.",
    },
    "exposure": {
        "drift": "Lysstyrke (brightness_mean) har flyttet sig markant de sidste {window_days} dage — kan skyldes støv/tåge på linsen, sæsonlys eller en kameraindstilling der er ændret.",
        "ok": "Ingen usædvanlig ændring i lysstyrke for perioden.",
        "insufficient": "Ikke nok billeder med brightness_mean i begge vinduer til en pålidelig sammenligning endnu.",
    },
    "white_balance": {
        "drift": "Hvidbalance-farvestik (cast_strength) er blevet markant stærkere de sidste {window_days} dage — muligt tegn på linsebelægning eller sensor-drift.",
        "ok": "Ingen usædvanlig ændring i hvidbalance for perioden.",
        "insufficient": "Ikke nok billeder med et hvidbalance-signal i begge vinduer endnu (kræver at Edge's optimizer har kørt).",
    },
}


def _analyse_dimension(
    db: Session,
    capture_model,
    camera_id: str,
    dimension: DimensionKey,
    dim_config: dict,
    *,
    now: datetime | None = None,
) -> DriftResult:
    field_name, worse_direction = _DIMENSION_FIELD[dimension]
    enabled = bool(dim_config.get("enabled", False))
    result = DriftResult(dimension=dimension, enabled=enabled, sufficient_data=False, config=dim_config)
    if not enabled:
        result.message = "Slået fra i config-hierakiet."
        return result

    now = now or datetime.now(timezone.utc)
    window_days = int(dim_config.get("window_days", 7))
    baseline_days = int(dim_config.get("baseline_days", 30))
    z_threshold = float(dim_config.get("z_threshold", 2.0))
    min_samples = int(dim_config.get("min_samples", 5))

    recent_cutoff = now - timedelta(days=window_days)
    baseline_cutoff = now - timedelta(days=window_days + baseline_days)
    column = getattr(capture_model, field_name)

    rows = (
        db.query(capture_model.captured_at, column)
        .filter(
            capture_model.camera_id == camera_id,
            capture_model.captured_at.isnot(None),
            column.isnot(None),
            capture_model.captured_at >= baseline_cutoff,
            capture_model.captured_at <= now,
        )
        .all()
    )

    # SQLite (bruges i tests) returnerer naive datetimes selv når det man
    # filtrerede med var tz-aware; Postgres (produktion) er typisk tz-aware
    # hele vejen. _naive_utc() normaliserer begge sider til naiv UTC, så
    # Python-side-sammenligningen nedenfor virker uanset driver.
    recent_cutoff_naive = _naive_utc(recent_cutoff)
    baseline_values = [float(v) for ts, v in rows if ts is not None and _naive_utc(ts) < recent_cutoff_naive]
    recent_values = [float(v) for ts, v in rows if ts is not None and _naive_utc(ts) >= recent_cutoff_naive]

    trend = _trend_shift(
        baseline_values, recent_values,
        worse_direction=worse_direction,
        z_threshold=z_threshold,
        min_samples=min_samples,
    )
    result.sufficient_data = trend["sufficient_data"]
    result.baseline_n = trend["baseline_n"]
    result.recent_n = trend["recent_n"]
    if not trend["sufficient_data"]:
        result.message = _MESSAGES[dimension]["insufficient"]
        return result

    result.baseline_mean = trend["baseline_mean"]
    result.baseline_stdev = trend["baseline_stdev"]
    result.recent_mean = trend["recent_mean"]
    result.delta = trend["delta"]
    result.z_score = trend["z_score"]
    result.drift_suspected = trend["drift_suspected"]
    key = "drift" if trend["drift_suspected"] else "ok"
    result.message = _MESSAGES[dimension][key].format(window_days=window_days, baseline_days=baseline_days)
    return result


def analyse_camera_drift(
    db: Session,
    capture_model,
    camera_id: str,
    raw_config: dict | None,
    *,
    now: datetime | None = None,
) -> dict:
    """Kør drift-analyse for alle tre dimensioner for ét kamera.

    Parametre:
      db: aktiv SQLAlchemy-session.
      capture_model: database.Capture-klassen (overføres af kalderen for at
        undgå cirkulær import mellem headend/main.py og headend/ai/*).
      camera_id: Camera.id (samme id som _resolve_config_hierarchy bruger).
      raw_config: DET RESOLVEREDE (global→kunde→site→kamera) effective_config
        fra _resolve_config_hierarchy — IKKE et rå lag. Kalderen har allerede
        gjort arve-arbejdet; denne funktion slår kun quality.drift_detection.*
        op i det færdige resultat.

    Returnerer et dict med én nøgle pr. dimension, hver et DriftResult.as_dict().
    Ingen sideeffekter, ingen skrivning til databasen, ingen kamerakommandoer.
    """
    dim_configs = _resolve_drift_config(raw_config)
    return {
        dim: _analyse_dimension(db, capture_model, camera_id, dim, dim_configs[dim], now=now).as_dict()
        for dim in dim_configs
    }
