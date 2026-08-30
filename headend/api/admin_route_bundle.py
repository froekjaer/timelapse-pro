"""Register extracted admin/trust API routes without growing main.py."""
from __future__ import annotations

from collections.abc import Callable

from api import customer_risk_api, grc_register_api, headend_generator_api, storage_api
from api.edge_communication_debug_api import install_edge_communication_logger, router as edge_communication_debug_router
from api.edge_lifecycle_api import create_edge_lifecycle_router
from api.trust_service_api import create_trust_service_router


def register_admin_route_bundle(
    app,
    require_role: Callable,
    sanitize_device_id: Callable,
    audit_key_event: Callable,
    reconcile_edge_lifecycle: Callable,
) -> None:
    app.include_router(customer_risk_api.router)
    app.include_router(grc_register_api.router)
    app.include_router(storage_api.router)
    app.include_router(headend_generator_api.router)
    app.include_router(edge_communication_debug_router)
    app.include_router(create_edge_lifecycle_router(
        require_role,
        sanitize_device_id,
        audit_key_event,
        reconcile_edge_lifecycle,
    ))
    app.include_router(create_trust_service_router(require_role))
    install_edge_communication_logger(app)
