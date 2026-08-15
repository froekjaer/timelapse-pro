"""Secure Service DMZ conduit specification.

This is a logical foundation only. WP-2 does not switch production traffic.
"""

from __future__ import annotations

SECURE_SERVICE_DMZ_SPEC = {
    "version": "2026-08-wp2-foundation",
    "zones": ["external", "dmz", "trust", "application", "data"],
    "allowed_conduits": [
        {"from": "external", "to": "dmz", "purpose": "edge_api_gateway"},
        {"from": "external", "to": "dmz", "purpose": "enrollment_gateway"},
        {"from": "external", "to": "dmz", "purpose": "update_distribution_gateway"},
        {"from": "dmz", "to": "trust", "purpose": "allowlisted_trust_api"},
        {"from": "dmz", "to": "application", "purpose": "allowlisted_application_api"},
        {"from": "trust", "to": "data", "purpose": "trust_owned_datastore"},
        {"from": "application", "to": "data", "purpose": "application_datastore"},
    ],
    "prohibited": [
        {"from": "dmz", "to": "data", "reason": "DMZ must not have direct unrestricted data-zone access"},
        {"from": "dmz", "to": "trust_private_keys", "reason": "DMZ is never a trust authority"},
        {"from": "external", "to": "trust", "reason": "Trust Service has no direct Internet exposure"},
        {"from": "external", "to": "data", "reason": "Data zone is not externally routable"},
    ],
    "dmz_may_issue": [],
    "trust_authority": "TimeLapse Trust Service",
}


def dmz_can_issue_trust_material() -> bool:
    return bool(SECURE_SERVICE_DMZ_SPEC["dmz_may_issue"])


def is_conduit_allowed(source: str, target: str, purpose: str) -> bool:
    return any(
        item["from"] == source and item["to"] == target and item["purpose"] == purpose
        for item in SECURE_SERVICE_DMZ_SPEC["allowed_conduits"]
    )
