"""Generic TimeLapse AI provider contract.

Product functions depend on capabilities, not concrete model vendors. Provider
adapters return observations/provenance; TimeLapse remains authoritative for
policy, RBAC, tenant scope, normalization and persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class AICapability(str, Enum):
    VISION = "vision"
    TEXT = "text"
    STRUCTURED = "structured"
    TOOL_CALLING = "tool_calling"
    LOCAL_EXECUTION = "local_execution"
    CLOUD_EXECUTION = "cloud_execution"


class AIProviderError(RuntimeError):
    """Base provider-layer error."""


class ProviderUnavailable(AIProviderError):
    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"{provider}: {reason}")


class NoEligibleProvider(AIProviderError):
    def __init__(self, capability: AICapability, attempts: list[dict[str, str]]):
        self.capability = capability
        self.attempts = attempts
        summary = ", ".join(
            f"{item.get('provider', '?')}={item.get('error_type', 'error')}"
            for item in attempts
        ) or "ingen providers"
        super().__init__(f"Ingen provider kunne levere {capability.value}: {summary}")


@dataclass(frozen=True)
class ProviderOutput:
    provider: str
    model: str
    capability: AICapability
    duration_ms: int
    content: str = ""
    data: dict[str, Any] | list[Any] | None = None
    raw_response: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def provenance(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "capability": self.capability.value,
            "duration_ms": self.duration_ms,
            **self.metadata,
        }


@runtime_checkable
class AIProvider(Protocol):
    name: str
    capabilities: frozenset[AICapability]

    def supports(self, capability: AICapability) -> bool:
        ...

    def availability(self, capability: AICapability) -> dict[str, Any]:
        ...

    def analyse_image(self, **kwargs):
        ...

    def generate_text(self, prompt: str, **kwargs) -> ProviderOutput:
        ...

    def generate_structured(self, prompt: str, **kwargs) -> ProviderOutput:
        ...
