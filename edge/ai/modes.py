"""
TimeLapse Pro edge AI mode policy.

The mode is configured under quality.edge_ai.mode and can be inherited from
global, customer, site or camera config. The policy deliberately separates
"what the image analysis sees" from "what the edge is allowed to change".
"""
from __future__ import annotations

from dataclasses import dataclass


MODE_OFF = "off"
MODE_MONITOR = "monitor"
MODE_ASSIST = "assist"
MODE_AUTONOMOUS = "autonomous"
MODE_NPU_FIRST = "npu_first"
MODE_LAB = "lab"

KNOWN_MODES = {
    MODE_OFF,
    MODE_MONITOR,
    MODE_ASSIST,
    MODE_AUTONOMOUS,
    MODE_NPU_FIRST,
    MODE_LAB,
}


@dataclass(frozen=True)
class EdgeAiPolicy:
    mode: str
    enabled: bool
    run_optimizer: bool
    run_npu: bool
    prefer_npu: bool
    emit_recommendations: bool
    allow_ev_autopilot: bool
    allow_camera_commands: bool
    allow_schedule_suggestions: bool
    confidence_floor: float

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "enabled": self.enabled,
            "run_optimizer": self.run_optimizer,
            "run_npu": self.run_npu,
            "prefer_npu": self.prefer_npu,
            "emit_recommendations": self.emit_recommendations,
            "allow_ev_autopilot": self.allow_ev_autopilot,
            "allow_camera_commands": self.allow_camera_commands,
            "allow_schedule_suggestions": self.allow_schedule_suggestions,
            "confidence_floor": self.confidence_floor,
        }


def edge_ai_policy(config: dict) -> EdgeAiPolicy:
    quality = config.get("quality", {}) or {}
    edge_ai = quality.get("edge_ai", {}) or {}
    raw_mode = str(edge_ai.get("mode") or quality.get("ai_mode") or MODE_ASSIST).strip().lower()
    mode = raw_mode if raw_mode in KNOWN_MODES else MODE_ASSIST
    enabled = bool(edge_ai.get("enabled", True)) and mode != MODE_OFF
    prefer_npu = bool(edge_ai.get("prefer_npu", True)) or mode == MODE_NPU_FIRST

    if not enabled:
        return EdgeAiPolicy(
            mode=MODE_OFF,
            enabled=False,
            run_optimizer=False,
            run_npu=False,
            prefer_npu=False,
            emit_recommendations=False,
            allow_ev_autopilot=False,
            allow_camera_commands=False,
            allow_schedule_suggestions=False,
            confidence_floor=1.0,
        )

    if mode == MODE_MONITOR:
        return EdgeAiPolicy(
            mode=mode,
            enabled=True,
            run_optimizer=True,
            run_npu=prefer_npu,
            prefer_npu=prefer_npu,
            emit_recommendations=True,
            allow_ev_autopilot=False,
            allow_camera_commands=False,
            allow_schedule_suggestions=False,
            confidence_floor=0.95,
        )

    if mode == MODE_ASSIST:
        return EdgeAiPolicy(
            mode=mode,
            enabled=True,
            run_optimizer=True,
            run_npu=prefer_npu,
            prefer_npu=prefer_npu,
            emit_recommendations=True,
            allow_ev_autopilot=True,
            allow_camera_commands=False,
            allow_schedule_suggestions=True,
            confidence_floor=0.70,
        )

    if mode == MODE_LAB:
        return EdgeAiPolicy(
            mode=mode,
            enabled=True,
            run_optimizer=True,
            run_npu=prefer_npu,
            prefer_npu=prefer_npu,
            emit_recommendations=True,
            allow_ev_autopilot=True,
            allow_camera_commands=True,
            allow_schedule_suggestions=True,
            confidence_floor=0.62,
        )

    return EdgeAiPolicy(
        mode=mode,
        enabled=True,
        run_optimizer=True,
        run_npu=True,
        prefer_npu=prefer_npu,
        emit_recommendations=True,
        allow_ev_autopilot=True,
        allow_camera_commands=mode == MODE_NPU_FIRST,
        allow_schedule_suggestions=True,
        confidence_floor=0.68 if mode == MODE_AUTONOMOUS else 0.65,
    )
