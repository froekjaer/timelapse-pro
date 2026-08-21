# Code Review Findings

## P1 — Technician auth confirmation SQL likely fails at runtime

**File:** `edge/technician_auth.py`  
**Evidence:** `confirm_session()` builds an `UPDATE technician_sessions ... WHERE session_id = ? WHERE session_id = ?`.

Impact:

- central Headend-confirmed technician login can fail when persisting confirmed sessions;
- EdgeServiceGrant-based normal service path may be unavailable even though ServicePlatform itself is sound;
- operators may fall back to legacy/offline/break-glass paths.

Recommended fix:

- remove duplicate `WHERE session_id = ?`;
- add deterministic test for `confirm_session()` persisting grant id/token/expiry and clearing `headend_session_token`;
- add test that confirmed session can start/use ServicePlatform where applicable.

## P1 — Break-glass remains partially operational rather than fully closed

Evidence from latest handover:

- RBAC-scoped technician SSH key model is implemented in code;
- live devices may not yet be provisioned with the new device-side user/sudoers/sshd wiring;
- password-based `BreakGlassAccount` remains selected but not end-to-end complete;
- shared legacy `orangepi` / `timelapse_headend_ed25519` access still exists side-by-side.

Impact:

- emergency access may be less reliable than documented;
- daily support path and emergency path remain easier to confuse;
- auditability and least privilege are not yet where the locked architecture wants them.

Recommended fix:

- finish device-side provisioning on live Edges after safe access plan;
- register Peter/operator personal technician keys;
- complete password break-glass propagation/rotation/revocation or explicitly de-scope it.

## P1 — GRC DB connectivity for AI/operator workflows is brittle

During this audit, direct `psql` using default environment failed with `database "peter" does not exist`. Earlier GRC state was available, but this specific shell lacked the configured connection.

Impact:

- agents can miss existing findings/actions and recreate work;
- OP-001 "recover existing context" weakens when GRC access path is not stable.

Recommended fix:

- document canonical local command/env for read-only GRC query;
- add a small `make grc-status` or script that fails with an explanatory message;
- avoid hiding GRC behind unstated shell state.

## P2 — `ServicePlatform.shared_or_lab_session()` calls `current_session()` twice

**File:** `edge/service_platform.py`

Impact:

- harmless functionally, but indicates low-level cleanup needed;
- can double-trigger cleanup in edge cases where current session expires during check.

Recommended fix:

- remove duplicate call and add a small regression test if touching file.

## P2 — Headend still has a very large monolithic `main.py`

Evidence:

- `headend/main.py` remains around the architecture ratchet limit;
- new routers exist, but many security-sensitive route groups still include from main.

Impact:

- high regression risk;
- review burden is large;
- boundary drift is likely.

Recommended fix:

- keep ratchet strict;
- only extract along existing router/service seams;
- do not do a big-bang rewrite before RC1.

## P2 — Remaining ad hoc authorization paths need closure

`Dokumentation/WP2_AD_HOC_AUTHORIZATION_PATHS_2026-08.md` identifies remaining modules:

- `headend/api/customer_risk_api.py`
- `headend/api/capture_access_api.py`
- `headend/api/grc_register_api.py`
- `headend/api/storage_api.py`
- `headend/api/headend_generator_api.py`
- `headend/api/edge_local_pki_api.py`

Impact:

- route-auth test proves authentication coverage, not complete PDP convergence;
- tenant/resource/capability/MFA semantics may still be inconsistent per route.

Recommended fix:

- close these one router at a time through PDP compatibility layer;
- keep route auth coverage as non-negotiable CI ratchet.

## P2 — `edge/technician_ui.py` is retired but still contains legacy HTTP handler code

The module says it never starts an unauthenticated listener, but the file still carries old handler implementation.

Impact:

- future maintainers may accidentally revive a retired surface;
- static scanners and reviewers will keep flagging it.

Recommended fix:

- replace with a minimal import-compatible stub when no current dependency needs handler internals;
- add test that no startup entrypoint launches it in production.

## P2 — Edge local PKI still has Headend-generated leaf key path

`headend/services/edge_local_pki.py::issue_local_edge_server_certificate()` still returns `private_key_pem`. WP-4 target says Edge-generated TLS private key + CSR.

Impact:

- acceptable only as legacy/migration/support path;
- not acceptable for new Edges once WP-4 target path is authoritative.

Recommended fix:

- mark this route explicitly legacy/migration if it is still exposed;
- prefer CSR signing path for all new Edges;
- test that new provisioning cannot use Headend-generated leaf private key.

## P3 — Minor code hygiene

Examples:

- generated `__pycache__` and backup files are present in working tree paths;
- some tests still use source-inspection assertions rather than behavior tests;
- user-facing Danish/English strings are mixed in several operational paths.

These are not blockers, but should be cleaned as part of stabilization.

