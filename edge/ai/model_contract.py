"""
Stable TimeLapse Edge QA model contract.

The NPU model is allowed to be vendor-specific, but the rest of the product
should only depend on this small vocabulary and JSON shape.
"""
from __future__ import annotations

import dataclasses
from typing import Any


SCHEMA_VERSION = "timelapse.edge_qa.v1"
MODEL_INPUT_CONTRACT = {
    "width": 224,
    "height": 224,
    "channels": 3,
    "layout": "NHWC",
    "color_order": "RGB",
    "scale": 1.0 / 255.0,
}


@dataclasses.dataclass(frozen=True)
class QaClassSpec:
    label: str
    class_id: int
    probable_cause: str
    quality_dimension: str
    recommended_action: str
    anomaly: bool = True

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


QA_CLASSES: tuple[QaClassSpec, ...] = (
    QaClassSpec(
        "ok",
        0,
        "ok",
        "overall",
        "Ingen handling.",
        anomaly=False,
    ),
    QaClassSpec(
        "blurry",
        1,
        "focus_or_lens_issue",
        "focus",
        "Kør LAB focus slice og kontroller dug, snavs eller fokusdrift.",
    ),
    QaClassSpec(
        "depth_of_field_issue",
        2,
        "depth_of_field_issue",
        "depth_of_field",
        "Stop objektivet et trin ned eller valider fokusplanet i LAB.",
    ),
    QaClassSpec(
        "snow_or_dirt_on_lens",
        3,
        "snow_or_dirt_on_lens",
        "lens_obstruction",
        "Kontroller frontglas/linse for sne, skidt eller saltfilm.",
    ),
    QaClassSpec(
        "condensation",
        4,
        "condensation_or_soft_lens_obstruction",
        "lens_obstruction",
        "Kontroller dug, varmelegeme og tæthed omkring frontglas.",
    ),
    QaClassSpec(
        "direct_sun_reflection",
        5,
        "direct_sun_reflection",
        "schedule",
        "Flyt capturetidspunkt via headend avoid-window eller sænk EV.",
    ),
    QaClassSpec(
        "underexposed",
        6,
        "underexposure_or_camera_blocked",
        "exposure",
        "Øg EV eller kontroller objektivdæksel, wakeup og lysforhold.",
    ),
    QaClassSpec(
        "overexposed",
        7,
        "overexposure_or_direct_sun",
        "exposure",
        "Sænk EV og kontroller solretning, refleksioner og montagevinkel.",
    ),
    QaClassSpec(
        "white_balance_cast",
        8,
        "white_balance_cast",
        "white_balance",
        "Fastlås hvidbalance efter dagslys/overskyet profil og re-test.",
    ),
)

LABEL_TO_SPEC = {spec.label: spec for spec in QA_CLASSES}
CLASS_ID_TO_SPEC = {spec.class_id: spec for spec in QA_CLASSES}

PROBABLE_CAUSE_TO_LABEL = {
    "ok": "ok",
    "focus_or_lens_issue": "blurry",
    "depth_of_field_issue": "depth_of_field_issue",
    "snow_or_dirt_on_lens": "snow_or_dirt_on_lens",
    "condensation_or_soft_lens_obstruction": "condensation",
    "direct_sun_reflection": "direct_sun_reflection",
    "underexposure_or_camera_blocked": "underexposed",
    "overexposure_or_direct_sun": "overexposed",
    "white_balance_cast": "white_balance_cast",
}

FILENAME_HINTS = (
    ("normal_balanced", "ok"),
    ("ok", "ok"),
    ("blurry", "blurry"),
    ("focus", "blurry"),
    ("shallow_depth_of_field", "depth_of_field_issue"),
    ("depth_of_field", "depth_of_field_issue"),
    ("dirty_lens", "snow_or_dirt_on_lens"),
    ("dirt_on_lens", "snow_or_dirt_on_lens"),
    ("snow_or_dirty_lens", "snow_or_dirt_on_lens"),
    ("snow_or_dirt_on_lens", "snow_or_dirt_on_lens"),
    ("condensation", "condensation"),
    ("direct_sun_reflection", "direct_sun_reflection"),
    ("sun_reflection", "direct_sun_reflection"),
    ("underexposed", "underexposed"),
    ("overexposed", "overexposed"),
    ("white_balance", "white_balance_cast"),
    ("cool_white_balance", "white_balance_cast"),
    ("warm_white_balance", "white_balance_cast"),
)


def validate_label(label: str) -> QaClassSpec:
    key = str(label or "").strip()
    if key not in LABEL_TO_SPEC:
        raise ValueError(f"Unknown edge QA label: {label!r}")
    return LABEL_TO_SPEC[key]


def label_from_class_id(class_id: int) -> str:
    try:
        return CLASS_ID_TO_SPEC[int(class_id)].label
    except Exception as exc:
        raise ValueError(f"Unknown edge QA class_id: {class_id!r}") from exc


def label_from_probable_cause(probable_cause: str | None, default: str = "ok") -> str:
    return PROBABLE_CAUSE_TO_LABEL.get(str(probable_cause or "").strip(), default)


def label_from_filename(name: str, default: str = "ok") -> str:
    lowered = str(name).lower()
    for needle, label in FILENAME_HINTS:
        if needle in lowered:
            return label
    return default


def classification_to_contract(
    label: str,
    confidence: float,
    *,
    engine: str = "edge_npu_model_v1",
    available: bool = True,
    source: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = validate_label(label)
    payload: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "engine": engine,
        "available": bool(available),
        "is_anomaly": spec.anomaly,
        "label": spec.label,
        "class_id": spec.class_id,
        "probable_cause": spec.probable_cause,
        "quality_dimension": spec.quality_dimension,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 4),
        "recommended_action": spec.recommended_action,
        "model_input": MODEL_INPUT_CONTRACT,
    }
    if source:
        payload["source"] = source
    if extra:
        payload.update(extra)
    return payload


def scores_to_contract(
    scores: dict[str, float] | list[float],
    *,
    engine: str = "edge_npu_model_v1",
    available: bool = True,
    source: str | None = None,
) -> dict[str, Any]:
    if isinstance(scores, dict):
        if not scores:
            raise ValueError("scores must not be empty")
        label, value = max(scores.items(), key=lambda item: float(item[1]))
        ordered_scores = {validate_label(k).label: round(float(v), 6) for k, v in scores.items()}
    else:
        if not scores:
            raise ValueError("scores must not be empty")
        class_id, value = max(enumerate(scores), key=lambda item: float(item[1]))
        label = label_from_class_id(class_id)
        ordered_scores = {
            CLASS_ID_TO_SPEC[idx].label: round(float(v), 6)
            for idx, v in enumerate(scores)
            if idx in CLASS_ID_TO_SPEC
        }
    return classification_to_contract(
        label,
        float(value),
        engine=engine,
        available=available,
        source=source,
        extra={"scores": ordered_scores},
    )


def contract_metadata() -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "model_input": MODEL_INPUT_CONTRACT,
        "classes": [spec.as_dict() for spec in QA_CLASSES],
    }
