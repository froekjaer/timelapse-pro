# WP-2 remaining ad hoc authorization paths

Dato: 2026-08-15

Scope: TimeLapse Trust Service, central PDP, EdgeServiceGrant og Secure Service DMZ foundation.

## Status

WP-2 flytter lokal technician service-adgang til EdgeServiceGrant og indfører `trust.policy.evaluate_legacy_role_capability_check()` som compatibility layer for gamle role/capability checks.

Secure Service DMZ er fortsat ikke-authoritative: DMZ må kun validere og route via Trust Service; den må ikke holde CA private keys og må ikke have direkte data-zone adgang.

## Migreret i WP-2

- `headend/api/trust_service_api.py` bruger `principal_from_legacy_user()` og `issue_edge_service_grant()`.
- `headend/api/service_access_api.py` kalder PDP compatibility layer efter device-scope check.
- `headend/main.py` technician-auth confirm udsteder kortlivet EdgeServiceGrant og returnerer ikke en normal Headend session til Edge.
- `edge/technician_auth.py` purger legacy `headend_session_token`, gemmer EdgeServiceGrant metadata og fail-closer ved revoke/expiry snapshot.
- `/api/config/{device_id}` eksponerer read-only EdgeServiceGrant status snapshot til Edge under `security.edge_service_grants`.

## Resterende ad hoc paths

Disse er bevidst ikke bredt refaktoreret i WP-2, men skal videreføres gennem PDP compatibility layer i senere work packages:

- `headend/main.py::require_role()` og `_ensure_customer_access()` / `_ensure_site_access()`.
- `headend/main.py` capture-, update-, OpenWebUI- og platform-admin checks med direkte `role`/`customer_id` beslutninger.
- `headend/cmdb.py::_require_cmdb_role()` og break-glass checkout policy.
- `headend/siem.py::_require_siem_role()`.
- `headend/itim.py::_require_role()` og `_ensure_target_access()`.
- `headend/api/customer_risk_api.py`, `capture_access_api.py`, `grc_register_api.py`, `storage_api.py`, `headend_generator_api.py` og `edge_local_pki_api.py`.
- `headend/ai/integration.py` og `headend/ai/settings_api.py`.

Baseline scan den 2026-08-15 fandt 99 relevante forekomster af lokale role/access/403-mønstre i `headend/`.

## WP-2 exit boundary

WP-2 stopper her før Local Service Gateway, browser terminal, generator split og CSR/PKI redesign. De resterende paths er en enumereret migration backlog, ikke et nyt authority-lag.
