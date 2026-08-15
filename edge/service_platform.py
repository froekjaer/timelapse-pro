"""Unified local technician service platform for Edge operations."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_STATE_DIR = Path(os.getenv("TIMELAPSE_SERVICE_STATE_DIR", "/run/timelapse"))
if not os.access(DEFAULT_STATE_DIR.parent, os.W_OK):
    DEFAULT_STATE_DIR = Path("/tmp/timelapse-service")


@dataclass(frozen=True)
class Principal:
    username: str
    role: str = "technician"
    capabilities: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class EdgeServiceGrantRef:
    grant_id: str
    expires_at: float
    revoked: bool = False


@dataclass
class ServiceSession:
    session_id: str
    principal: Principal
    grant: EdgeServiceGrantRef
    capabilities: frozenset[str]
    created_at: float
    last_activity: float
    idle_timeout_s: int = 900
    absolute_timeout_s: int = 3600
    active: bool = True
    invalidation_reason: str | None = None

    def check_active(self, now: float | None = None) -> None:
        now = now or time.time()
        if not self.active:
            raise PermissionError(f"service session inactive: {self.invalidation_reason or 'inactive'}")
        if self.grant.revoked:
            self.invalidate("grant_revoked")
        elif now >= self.grant.expires_at:
            self.invalidate("grant_expired")
        elif now - self.last_activity > self.idle_timeout_s:
            self.invalidate("idle_timeout")
        elif now - self.created_at > self.absolute_timeout_s:
            self.invalidate("absolute_timeout")
        if not self.active:
            raise PermissionError(f"service session inactive: {self.invalidation_reason}")

    def touch(self, now: float | None = None) -> None:
        self.last_activity = now or time.time()

    def invalidate(self, reason: str) -> None:
        self.active = False
        self.invalidation_reason = reason


@dataclass(frozen=True)
class OperationSpec:
    name: str
    capability: str
    lease_type: str | None = None
    handler: Callable[["ServicePlatform", ServiceSession, dict[str, Any]], dict[str, Any]] | None = None


LEASE_TYPES = {
    "CameraPowerLease",
    "LiveViewLease",
    "TemporaryConfigLease",
    "DiagnosticLease",
    "ModemMaintenanceLease",
}


OPERATION_CAPABILITIES = {
    "camera.status": "camera.read",
    "camera.detect": "camera.hardware",
    "camera.ptp.diagnostics": "camera.diagnostics",
    "camera.power.acquire": "camera.power",
    "camera.power.release": "camera.power",
    "camera.power.cycle": "camera.power",
    "camera.capture.test": "camera.capture.test",
    "camera.live.start": "camera.live",
    "camera.live.stop": "camera.live",
    "camera.config.read": "camera.config.read",
    "camera.config.diff": "camera.config.read",
    "camera.config.set_temporary": "camera.config.temporary",
    "camera.usb.rediscover": "camera.hardware",
    "camera.driver.reconnect": "camera.hardware",
    "camera.hardware.inventory": "camera.hardware",
    "camera.focus.manual": "camera.focus",
    "camera.focus.auto": "camera.focus",
    "camera.exposure.test": "camera.exposure",
    "image.quality.diagnostics": "camera.diagnostics",
    "camera.reset": "camera.reset",
    "camera.diagnostics": "camera.diagnostics",
    "modem.status": "modem.read",
    "modem.signal": "modem.read",
    "modem.registration": "modem.read",
    "modem.reconnect_history": "modem.read",
    "modem.power.cycle": "modem.power",
    "network.status": "network.read",
    "network.diagnostics": "network.read",
    "storage.status": "storage.read",
    "system.status": "system.read",
    "system.logs": "system.logs",
    "timelapse.service.status": "system.read",
    "timelapse.service.restart": "system.service.restart",
    "certificate.trust.status": "trust.read",
    "trust.ssh_host_identity": "trust.read",
    "software.update.status": "software.read",
    "diagnostic.bundle": "system.logs",
    "system.reboot": "system.reboot",
    "commissioning.run": "commissioning.run",
    "commissioning.validate": "commissioning.validate",
}


OPERATION_LEASES = {
    "camera.status": "CameraPowerLease",
    "camera.detect": "CameraPowerLease",
    "camera.ptp.diagnostics": "CameraPowerLease",
    "camera.power.acquire": "CameraPowerLease",
    "camera.power.cycle": "CameraPowerLease",
    "camera.capture.test": "CameraPowerLease",
    "camera.live.start": "LiveViewLease",
    "camera.config.read": "CameraPowerLease",
    "camera.config.diff": "DiagnosticLease",
    "camera.config.set_temporary": "TemporaryConfigLease",
    "camera.usb.rediscover": "CameraPowerLease",
    "camera.driver.reconnect": "CameraPowerLease",
    "camera.hardware.inventory": "CameraPowerLease",
    "camera.focus.manual": "CameraPowerLease",
    "camera.focus.auto": "CameraPowerLease",
    "camera.exposure.test": "CameraPowerLease",
    "image.quality.diagnostics": "DiagnosticLease",
    "camera.reset": "CameraPowerLease",
    "camera.diagnostics": "CameraPowerLease",
    "modem.power.cycle": "ModemMaintenanceLease",
}


TECHNICIAN_CAPABILITIES = frozenset({
    "camera.read",
    "camera.power",
    "camera.capture.test",
    "camera.live",
    "camera.config.read",
    "camera.config.temporary",
    "camera.hardware",
    "camera.focus",
    "camera.exposure",
    "camera.diagnostics",
    "modem.read",
    "network.read",
    "storage.read",
    "system.read",
    "system.logs",
    "trust.read",
    "software.read",
    "commissioning.validate",
})


SENIOR_TECHNICIAN_CAPABILITIES = TECHNICIAN_CAPABILITIES | frozenset({
    "modem.power",
    "camera.reset",
    "system.service.restart",
    "commissioning.run",
})
ENGINEER_CAPABILITIES = SENIOR_TECHNICIAN_CAPABILITIES | frozenset({"system.reboot"})
BREAK_GLASS_CAPABILITIES = ENGINEER_CAPABILITIES | frozenset({"break_glass"})
LAB_CAPABILITIES = SENIOR_TECHNICIAN_CAPABILITIES | frozenset({"lab"})


class ServicePlatform:
    def __init__(self, state_dir: Path | None = None, audit_path: Path | None = None):
        self.state_dir = Path(state_dir or DEFAULT_STATE_DIR)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / "service_session.json"
        self.audit_path = audit_path or (self.state_dir / "service_audit.jsonl")
        self.acquire_handlers: dict[str, Callable[["ServicePlatform", ServiceSession, str], None]] = {}
        self.cleanup_handlers: dict[str, Callable[["ServicePlatform", ServiceSession, str], None]] = {}
        self.operations = {
            name: OperationSpec(name, capability, OPERATION_LEASES.get(name), self._default_handler)
            for name, capability in OPERATION_CAPABILITIES.items()
        }

    def start_session(
        self,
        *,
        principal: Principal,
        grant: EdgeServiceGrantRef,
        idle_timeout_s: int = 900,
        absolute_timeout_s: int = 3600,
    ) -> ServiceSession:
        now = time.time()
        session = ServiceSession(
            session_id=f"TLP-SVC-{uuid.uuid4().hex[:16]}",
            principal=principal,
            grant=grant,
            capabilities=principal.capabilities,
            created_at=now,
            last_activity=now,
            idle_timeout_s=idle_timeout_s,
            absolute_timeout_s=absolute_timeout_s,
        )
        self._save({"session": self._session_dict(session), "leases": {}, "temporary_state": {}, "camera_config_dirty": []})
        self.audit(session, "session.start", "edge:local-service", None, self.status(), "success")
        return session

    def start_session_from_edge_service_grant(
        self,
        *,
        username: str,
        role: str,
        grant_id: str,
        expires_at: float,
        capabilities: set[str] | frozenset[str] | list[str] | tuple[str, ...],
        idle_timeout_s: int = 900,
        absolute_timeout_s: int = 3600,
    ) -> ServiceSession:
        """Start a normal ServiceSession from a WP-2 EdgeServiceGrant."""
        if not grant_id or grant_id.startswith(("local-", "lab-", "offline-recovery-")):
            raise PermissionError("valid EdgeServiceGrant required")
        if time.time() >= float(expires_at):
            raise PermissionError("EdgeServiceGrant expired")
        caps = frozenset(capabilities)
        if not caps:
            raise PermissionError("EdgeServiceGrant has no service capabilities")
        return self.start_session(
            principal=Principal(username=username, role=role, capabilities=caps),
            grant=EdgeServiceGrantRef(grant_id=grant_id, expires_at=float(expires_at)),
            idle_timeout_s=idle_timeout_s,
            absolute_timeout_s=absolute_timeout_s,
        )

    def start_lab_session(self) -> ServiceSession:
        """Start the explicit LAB authority adapter."""
        return self.start_session(
            principal=Principal(username="lab", role="lab", capabilities=LAB_CAPABILITIES),
            grant=EdgeServiceGrantRef(grant_id=f"lab-{uuid.uuid4().hex[:16]}", expires_at=time.time() + 3600),
        )

    def start_offline_recovery_session(self, username: str = "offline-recovery") -> ServiceSession:
        """Start the explicit offline/break-glass TOTP compatibility authority."""
        return self.start_session(
            principal=Principal(username=username, role="offline_recovery", capabilities=BREAK_GLASS_CAPABILITIES),
            grant=EdgeServiceGrantRef(
                grant_id=f"offline-recovery-{uuid.uuid4().hex[:16]}",
                expires_at=time.time() + 3600,
            ),
        )

    def current_session(self) -> ServiceSession | None:
        state = self._load()
        raw = state.get("session")
        if not raw:
            return None
        session = self._session_from_dict(raw)
        try:
            session.check_active()
        except PermissionError:
            self.invalidate(session, session.invalidation_reason or "expired")
            return None
        return session

    def shared_or_lab_session(self, role: str = "technician") -> ServiceSession:
        existing = self.current_session()
        if existing:
            return existing
        if role == "lab":
            return self.start_lab_session()
        if role in {"offline_recovery", "break_glass"}:
            return self.start_offline_recovery_session(role)
        raise PermissionError("active EdgeServiceGrant-backed ServiceSession required")

    def register_handler(
        self,
        operation: str,
        handler: Callable[["ServicePlatform", ServiceSession, dict[str, Any]], dict[str, Any]],
    ) -> None:
        spec = self.operations.get(operation)
        if not spec:
            raise KeyError(f"unknown service operation: {operation}")
        self.operations[operation] = OperationSpec(spec.name, spec.capability, spec.lease_type, handler)

    def register_cleanup_handler(
        self,
        lease_type: str,
        handler: Callable[["ServicePlatform", ServiceSession, str], None],
    ) -> None:
        if lease_type not in LEASE_TYPES:
            raise KeyError(f"unknown lease type: {lease_type}")
        self.cleanup_handlers[lease_type] = handler

    def register_acquire_handler(
        self,
        lease_type: str,
        handler: Callable[["ServicePlatform", ServiceSession, str], None],
    ) -> None:
        if lease_type not in LEASE_TYPES:
            raise KeyError(f"unknown lease type: {lease_type}")
        self.acquire_handlers[lease_type] = handler

    def call(self, operation: str, session: ServiceSession | None = None, **kwargs) -> dict[str, Any]:
        session = session or self.current_session()
        if not session:
            raise PermissionError("service session required")
        try:
            session.check_active()
        except PermissionError:
            self.invalidate(session, session.invalidation_reason or "inactive")
            raise
        spec = self.operations.get(operation)
        if not spec:
            raise KeyError(f"unknown service operation: {operation}")
        if spec.capability not in session.capabilities:
            raise PermissionError(f"missing capability: {spec.capability}")
        before = self.status()
        if operation == "camera.live.start":
            self.acquire_lease(session, "CameraPowerLease", operation)
        if spec.lease_type:
            self.acquire_lease(session, spec.lease_type, operation)
        call_args = {"operation": operation, **kwargs}
        try:
            result = (spec.handler or self._default_handler)(self, session, call_args)
            if operation in {"camera.power.release", "camera.live.stop"}:
                lease = "LiveViewLease" if operation == "camera.live.stop" else "CameraPowerLease"
                self.release_lease(session, lease, operation)
                if operation == "camera.live.stop":
                    self.release_lease(session, "CameraPowerLease", operation)
            elif kwargs.get("release_after") and spec.lease_type:
                cleanup = self.cleanup_handlers.get(spec.lease_type)
                if cleanup:
                    cleanup(self, session, operation)
                self.release_lease(session, spec.lease_type, operation)
            session.touch()
            self._update_session(session)
            self.audit(session, operation, kwargs.get("resource", "edge:local-service"), before, self.status(), "success")
            return result
        except Exception:
            self.audit(session, operation, kwargs.get("resource", "edge:local-service"), before, self.status(), "failed")
            raise

    def acquire_lease(self, session: ServiceSession, lease_type: str, reason: str) -> dict:
        if lease_type not in LEASE_TYPES:
            raise KeyError(f"unknown lease type: {lease_type}")
        state = self._load()
        leases = state.setdefault("leases", {})
        lease = leases.get(lease_type)
        if lease and lease.get("session_id") != session.session_id:
            raise PermissionError(f"{lease_type} is owned by another ServiceSession")
        was_active = bool(lease and lease.get("active"))
        lease = lease or {
            "lease_id": f"TLP-LEASE-{uuid.uuid4().hex[:16]}",
            "lease_type": lease_type,
            "session_id": session.session_id,
            "created_at": _iso(time.time()),
        }
        lease.update({"active": True, "reason": reason, "last_activity": _iso(time.time())})
        leases[lease_type] = lease
        self._save(state)
        if not was_active:
            handler = self.acquire_handlers.get(lease_type)
            if handler:
                handler(self, session, reason)
        return lease

    def release_lease(self, session: ServiceSession, lease_type: str, reason: str) -> None:
        state = self._load()
        lease = state.get("leases", {}).get(lease_type)
        if lease and lease.get("session_id") == session.session_id:
            lease.update({"active": False, "released_at": _iso(time.time()), "release_reason": reason})
            self._save(state)

    def invalidate(self, session: ServiceSession | None = None, reason: str = "logout") -> dict[str, Any]:
        state = self._load()
        session = session or (self._session_from_dict(state["session"]) if state.get("session") else None)
        before = self.status()
        if session:
            self.release_all(session, reason)
            state = self._load()
        state["temporary_state"] = {}
        state["live_view"] = {"running": False, "stop_reason": reason}
        if state.get("session"):
            state["session"]["active"] = False
            state["session"]["invalidation_reason"] = reason
        self._save(state)
        if session:
            session.invalidate(reason)
            self.audit(session, "session.invalidate", "edge:local-service", before, self.status(), "success")
        return self.status()

    def release_all(self, session: ServiceSession, reason: str) -> None:
        state = self._load()
        leases = state.get("leases", {})
        active_leases = [
            lease_type for lease_type, lease in leases.items()
            if lease.get("session_id") == session.session_id and lease.get("active")
        ]
        for lease_type in ("LiveViewLease", "CameraPowerLease", "TemporaryConfigLease", "DiagnosticLease", "ModemMaintenanceLease"):
            if lease_type not in active_leases:
                continue
            handler = self.cleanup_handlers.get(lease_type)
            if handler:
                handler(self, session, reason)
            self.release_lease(session, lease_type, reason)

    def record_temporary_config_change(self, change: dict[str, Any]) -> None:
        state = self._load()
        dirty = state.setdefault("camera_config_dirty", [])
        dirty.append({"timestamp": _iso(time.time()), **change})
        self._save(state)

    def status(self) -> dict[str, Any]:
        state = self._load()
        session = state.get("session") or {}
        leases = state.get("leases") or {}
        camera_power = bool((leases.get("CameraPowerLease") or {}).get("active"))
        live_view = bool((leases.get("LiveViewLease") or {}).get("active"))
        now = time.time()
        grant_expires = _parse_ts(((session.get("grant") or {}).get("expires_at"))) if session else None
        session_expires = min(
            float(session.get("created_at", now)) + int(session.get("absolute_timeout_s", 0) or 0),
            float(session.get("last_activity", now)) + int(session.get("idle_timeout_s", 0) or 0),
        ) if session else None
        return {
            "schema": "timelapse.edge.service_status.v1",
            "logged_in": bool(session.get("active")),
            "session_id": session.get("session_id"),
            "principal": (session.get("principal") or {}).get("username"),
            "grant_id": (session.get("grant") or {}).get("grant_id"),
            "camera_relay_on": camera_power,
            "camera_detected": bool(state.get("camera_detected", camera_power)),
            "ptp_connected": bool(state.get("ptp_connected", camera_power)),
            "live_view": "ON" if live_view else "OFF",
            "config_dirty_count": len(state.get("camera_config_dirty") or []),
            "config_dirty": state.get("camera_config_dirty") or [],
            "session_expires_in_s": max(0, int(session_expires - now)) if session_expires else None,
            "grant_expires_in_s": max(0, int(grant_expires - now)) if grant_expires else None,
            "last_activity_s": max(0, int(now - float(session.get("last_activity", now)))) if session else None,
            "leases": leases,
        }

    def audit(self, session: ServiceSession, operation: str, resource: str, before, after, result: str) -> None:
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "principal": session.principal.username,
            "grant_id": session.grant.grant_id,
            "operation": operation,
            "resource": resource,
            "before": before,
            "after": after,
            "result": result,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def _default_handler(self, _platform: "ServicePlatform", _session: ServiceSession, kwargs: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "operation": kwargs.get("operation"), "status": self.status()}

    def _load(self) -> dict[str, Any]:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {"session": None, "leases": {}, "temporary_state": {}, "camera_config_dirty": []}

    def _save(self, state: dict[str, Any]) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def _update_session(self, session: ServiceSession) -> None:
        state = self._load()
        state["session"] = self._session_dict(session)
        self._save(state)

    def _session_dict(self, session: ServiceSession) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "principal": {"username": session.principal.username, "role": session.principal.role},
            "grant": {"grant_id": session.grant.grant_id, "expires_at": session.grant.expires_at, "revoked": session.grant.revoked},
            "capabilities": sorted(session.capabilities),
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "idle_timeout_s": session.idle_timeout_s,
            "absolute_timeout_s": session.absolute_timeout_s,
            "active": session.active,
            "invalidation_reason": session.invalidation_reason,
        }

    def _session_from_dict(self, raw: dict[str, Any]) -> ServiceSession:
        grant = raw.get("grant") or {}
        principal = raw.get("principal") or {}
        return ServiceSession(
            session_id=raw["session_id"],
            principal=Principal(principal.get("username", ""), principal.get("role", ""), frozenset(raw.get("capabilities") or [])),
            grant=EdgeServiceGrantRef(grant.get("grant_id", ""), float(grant.get("expires_at", 0)), bool(grant.get("revoked"))),
            capabilities=frozenset(raw.get("capabilities") or []),
            created_at=float(raw.get("created_at", time.time())),
            last_activity=float(raw.get("last_activity", time.time())),
            idle_timeout_s=int(raw.get("idle_timeout_s", 900)),
            absolute_timeout_s=int(raw.get("absolute_timeout_s", 3600)),
            active=bool(raw.get("active", True)),
            invalidation_reason=raw.get("invalidation_reason"),
        )


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _parse_ts(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return float(value)
    return 0.0
