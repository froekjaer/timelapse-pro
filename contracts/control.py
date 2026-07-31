"""Mission Platform contracts — control plane v1 (ADR-002).

The PayloadDriver is the single control-plane seam between the reusable platform
core and a replaceable payload (today: timelapse). The supervisor owns liveness
(health polling, restart, rollback); the driver owns its own cadence between
start() and stop().

This package is PURE: it must import nothing from headend/ or edge/. That
invariant is machine-enforced by tests/test_contracts_architecture.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

CONTROL_CONTRACT_VERSION = "1.0.0"


class ContractError(Exception):
    """Base for control-contract failures."""


class PolicyRejected(ContractError):
    """configure() got an invalid policy. Supervisor keeps the previous policy."""


class CommandRejected(ContractError):
    """handle_command() got an unknown/unauthorised command (fail closed)."""


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True)
class PayloadPolicy:
    revision: int
    settings: Mapping[str, Any]


@dataclass(frozen=True)
class HealthReport:
    status: HealthStatus
    detail: str = ""
    metrics: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Command:
    name: str
    args: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    detail: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)


class PayloadDriver(ABC):
    """Implemented by every payload. Timelapse is the first (edge/camera capture)."""

    @abstractmethod
    def configure(self, policy: PayloadPolicy) -> None:
        """Apply verified policy. Raise PolicyRejected on invalid policy."""

    @abstractmethod
    def start(self) -> None:
        """Begin domain work. Return promptly; cadence is driver-internal."""

    @abstractmethod
    def stop(self, deadline_s: float) -> None:
        """Stop within deadline_s seconds. Idempotent."""

    @abstractmethod
    def health(self) -> HealthReport:
        """Cheap, non-blocking health snapshot for the supervisor."""

    @abstractmethod
    def handle_command(self, cmd: Command) -> CommandResult:
        """Execute an allowlisted command. Unknown -> CommandRejected."""
