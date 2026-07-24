"""Fail-closed security policy for first Headend administrator bootstrap."""

from __future__ import annotations

import os


def resolve_initial_admin_password(environment: str, locked_environments: set[str], logger) -> str:
    initial_password = os.getenv("TIMELAPSE_INITIAL_ADMIN_PASSWORD", "").strip()
    if not initial_password and environment in locked_environments:
        raise RuntimeError(
            "TIMELAPSE_INITIAL_ADMIN_PASSWORD mangler; staging/prod må ikke "
            "oprette en super_admin med en kendt standardadgangskode"
        )
    if not initial_password:
        logger.critical(
            "R&D fallback: initial super_admin oprettes med kendt testpassword. "
            "Dette er forbudt i staging/prod."
        )
        return "changeme"
    return initial_password
