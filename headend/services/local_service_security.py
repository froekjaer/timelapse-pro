"""Fail-closed policy helpers for Edge local technician service."""

from __future__ import annotations


def enforce_local_service_totp_provisioning(cfg: dict) -> None:
    """Disable local service when no unique/provisioned TOTP seed is present.

    Explicit global/customer/site/device/camera secrets remain valid migration
    adapters.  The absence of a secret is not replaced by any shared factory
    credential.
    """
    bt_totp = cfg.get("bt_totp") if isinstance(cfg.get("bt_totp"), dict) else {}
    if bt_totp.get("secret"):
        return

    cfg["bt_totp"] = {"secret": "", "sid": "unprovisioned"}
    service_access = cfg.setdefault("service_access", {})
    if isinstance(service_access, dict):
        service_access["enabled"] = False
        service_access["live_view_enabled"] = False
        service_access["allow_continuous_live_view"] = False
        service_access["disabled_reason"] = "local_totp_unprovisioned"
