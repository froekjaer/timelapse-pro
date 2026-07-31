"""Supervisor — payload lifecycle under fail-closed governance.

Admission: parse manifest -> verify signed node policy -> policy check.
Any failure => payload never instantiated, audit event recorded.
Runtime: health polling with restart-backoff then quarantine (failure
contract, ADR-CL-004); every transition audited.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping

from contracts import CONTRACT_VERSIONS
from contracts.control import Command, CommandResult, HealthStatus, PayloadDriver, PayloadPolicy
from contracts.manifest import Manifest, ManifestRejected, check_against_policy, parse_manifest
from platform_host.policy import NodePolicy
from platform_host.spool import SpoolDataSink

DriverFactory = Callable[[Manifest, SpoolDataSink], PayloadDriver]


class PayloadState(str, Enum):
    ADMITTED = "admitted"
    RUNNING = "running"
    STOPPED = "stopped"
    QUARANTINED = "quarantined"
    REFUSED = "refused"


@dataclass
class AuditEvent:
    ts: float
    action: str
    outcome: str
    detail: str = ""


@dataclass
class ManagedPayload:
    manifest: Manifest
    driver: PayloadDriver
    sink: SpoolDataSink
    state: PayloadState
    restarts: int = 0


class Supervisor:
    MAX_RESTARTS = 3

    def __init__(self, node_policy: NodePolicy, spool_root: Path) -> None:
        self._policy = node_policy
        self._spool_root = spool_root
        self._payloads: dict[str, ManagedPayload] = {}
        self.audit_log: list[AuditEvent] = []

    def _audit(self, action: str, outcome: str, detail: str = "") -> None:
        self.audit_log.append(AuditEvent(time.time(), action, outcome, detail))

    # -- admission (fail closed) --------------------------------------------
    def admit(self, manifest_doc: Mapping[str, Any], factory: DriverFactory) -> ManagedPayload:
        try:
            manifest = parse_manifest(manifest_doc)
            check_against_policy(
                manifest,
                allowed_capabilities=self._policy.allowed_capabilities,
                quota_ceilings=self._policy.quota_ceilings,
                supported_majors=self._policy.supported_contract_majors,
            )
        except ManifestRejected as exc:
            self._audit("admit", "REFUSED", str(exc))
            raise
        sink = SpoolDataSink(manifest, self._spool_root / manifest.name)
        driver = factory(manifest, sink)
        managed = ManagedPayload(manifest, driver, sink, PayloadState.ADMITTED)
        self._payloads[manifest.name] = managed
        self._audit("admit", "OK", f"{manifest.name}@{manifest.version}")
        return managed

    # -- lifecycle -----------------------------------------------------------
    def configure_and_start(self, name: str, policy: PayloadPolicy) -> None:
        p = self._payloads[name]
        p.driver.configure(policy)  # PolicyRejected propagates; previous policy stays
        p.driver.start()
        p.state = PayloadState.RUNNING
        self._audit("start", "OK", name)

    def stop(self, name: str, deadline_s: float = 10.0) -> None:
        p = self._payloads[name]
        p.driver.stop(deadline_s)
        p.state = PayloadState.STOPPED
        self._audit("stop", "OK", name)

    def command(self, name: str, cmd: Command) -> CommandResult:
        result = self._payloads[name].driver.handle_command(cmd)
        self._audit("command", "OK" if result.ok else "REJECTED", f"{name}:{cmd.name}")
        return result

    # -- health / failure contract -------------------------------------------
    def health_check(self, name: str) -> PayloadState:
        p = self._payloads[name]
        if p.state is not PayloadState.RUNNING:
            return p.state
        report = p.driver.health()
        if report.status is HealthStatus.FAILED:
            p.restarts += 1
            if p.restarts > self.MAX_RESTARTS:
                p.driver.stop(deadline_s=5.0)
                p.state = PayloadState.QUARANTINED
                self._audit("health", "QUARANTINED", f"{name}: {report.detail}")
            else:
                p.driver.stop(deadline_s=5.0)
                p.driver.start()
                self._audit("health", "RESTARTED", f"{name} attempt {p.restarts}")
        return p.state

    def state(self, name: str) -> PayloadState:
        return self._payloads[name].state


def default_supported_majors() -> dict[str, int]:
    return {k: int(v.split(".")[0]) for k, v in CONTRACT_VERSIONS.items() if k != "manifest"}
