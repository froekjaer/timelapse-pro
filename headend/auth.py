# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — auth.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Shared auth/session/RBAC kernel, extracted from main.py (2026-08-26).

Before this module existed, every router file mounted by main.py that needed
auth (cmdb.py, edge_sync.py, siem.py, technician_keys.py, commissioning_key.py,
local_access.py, itim.py, redaction_api.py) had to work around a circular
import: main.py imports each of those modules at load time to mount them, so
none of them could import main.py's auth helpers at module scope — they all
did `from main import get_current_user, ...` INSIDE a function body instead,
duplicating the exact same import list across 8 files. A parallel, newer
pattern (`create_X_router(require_role, ...)` factory functions under
headend/api/) avoided the lazy import but pushed the same coupling into
main.py's `include_router(...)` call sites instead.

This module is the actual fix: it has no dependency on main.py or any router
module (only on `database.py` and third-party libs), so main.py AND every
router module can import it at module scope, same as they already import
`database.py`. New router modules should do `from auth import require_role,
get_current_user` directly — no lazy import, no factory-argument threading.

Montér i main.py — main.py no longer defines these names, it imports them:
    from auth import (
        TIMELAPSE_ENV, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_H,
        COOKIE_NAME, COOKIE_SECURE,
        _hash_password, _verify_password, _create_token, _decode_token,
        _cookie_header, _delete_cookie_header,
        _session_payload, _session_is_mfa_verified, _mfa_required_for_user,
        _user_has_totp, _user_has_partial_mfa,
        _AGENT_LOCKED_ENVIRONMENTS, _agent_role_blocked_in_this_environment,
        _log_agent_lockdown_status,
        _ensure_super_admin, _warn_if_default_admin_password_active,
        get_current_user, _ROLE_HIERARCHY, require_role,
    )

Everything here is moved VERBATIM from main.py (same names, same internals) —
this is deliberately a pure cut/paste, not a rewrite, to keep the regression
surface minimal: every existing `Depends(require_role(...))` call site in
main.py (235 routes) and every already-extracted router module keeps working
unchanged, only where these function bodies live has changed. In particular
`require_role(...)`'s inner closure keeps the name `_check` —
headend/tests/test_route_auth_coverage.py's
test_high_risk_admin_surfaces_use_role_authentication hardcodes that literal
dependency name for 8 specific high-risk paths; renaming it would silently
break that test with a confusing failure unrelated to the actual change.

Deliberately NOT included here (see Dokumentation — refactor plan,
2026-08-26): `_is_platform_admin`, `_visible_device_query`,
`_visible_camera_query`, `_verify_device_token`, `_ensure_capture_device_access`.
Different files depend on different subsets of those, and they're a distinct
"tenant scoping" concern from this module's "who is this user, are they
authenticated, what role do they have" scope — a fast-follow extraction once
this module has proven itself.
"""
from __future__ import annotations

import logging
import os
import secrets as _secrets
from datetime import timedelta

import bcrypt as _bcrypt_lib
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt as _jwt
from sqlalchemy.orm import Session

from database import Camera, ConfigDefaults, Customer, Site, User, get_db, now_utc
from services.bootstrap_security import resolve_initial_admin_password
from dict_merge import _deep_merge

log = logging.getLogger("headend")

# ═══════════════════════════════════════════════════════════════════════════
# ── AUTH / RBAC ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

TIMELAPSE_ENV = os.getenv("TIMELAPSE_ENV", "lab").strip().lower()
_jwt_secret_from_env = os.getenv("JWT_SECRET")
if TIMELAPSE_ENV in {"prod", "production"}:
    if not _jwt_secret_from_env or len(_jwt_secret_from_env) < 32:
        raise RuntimeError(
            "JWT_SECRET must be explicitly set to at least 32 characters in production"
        )

JWT_SECRET    = _jwt_secret_from_env or _secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_H  = 12   # access token levetid
COOKIE_NAME   = "tl_session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"


def _hash_password(pw: str) -> str:
    return _bcrypt_lib.hashpw(pw.encode(), _bcrypt_lib.gensalt()).decode()

def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt_lib.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def _create_token(data: dict, expire_hours: int = JWT_EXPIRE_H) -> str:
    payload = data.copy()
    payload["exp"] = now_utc() + timedelta(hours=expire_hours)
    return _jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def _decode_token(token: str) -> dict | None:
    try:
        return _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None

def _cookie_header(name: str, value: str, max_age: int, *, domain: str | None = None) -> str:
    parts = [
        f"{name}={value}",
        "Path=/",
        "HttpOnly",
        "SameSite=Lax",
        f"Max-Age={max_age}",
    ]
    if domain:
        parts.append(f"Domain={domain}")
    if COOKIE_SECURE:
        parts.append("Secure")
    return "; ".join(parts)

def _delete_cookie_header(name: str, *, domain: str | None = None) -> str:
    parts = [
        f"{name}=",
        "Path=/",
        "HttpOnly",
        "Max-Age=0",
        "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
    ]
    if domain:
        parts.append(f"Domain={domain}")
    if COOKIE_SECURE:
        parts.append("Secure")
    return "; ".join(parts)

def _session_payload(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    return _decode_token(token) if token else None

def _session_is_mfa_verified(payload: dict | None) -> bool:
    if not payload:
        return False
    if payload.get("mfa_verified") is True:
        return True
    amr = payload.get("amr") or []
    if isinstance(amr, str):
        amr = [amr]
    return bool({"totp", "webauthn", "passkey", "fido2"}.intersection(set(amr)))


_SESSION_POLICY_DEFAULTS = {
    "session_duration_hours": 12,
    "remember_me_days":       30,
    "absolute_max_days":      90,
    "rolling_enabled":        True,
    "remember_me_allowed":    True,
    "mfa_required":           False,
    "webauthn_required":      False,
    "mfa_required_by_role": {
        "super_admin": True,
        "admin":       True,
        "operator":    False,
        "viewer":      False,
    },
    "mfa_exempt_usernames": [],
}


def _normalise_session_policy(policy: dict | None) -> dict:
    merged = _deep_merge(_SESSION_POLICY_DEFAULTS, policy or {})
    role_defaults = dict(_SESSION_POLICY_DEFAULTS["mfa_required_by_role"])
    role_defaults.update((merged.get("mfa_required_by_role") or {}))
    merged["mfa_required_by_role"] = role_defaults
    exemptions = merged.get("mfa_exempt_usernames") or []
    if isinstance(exemptions, str):
        exemptions = [v.strip() for v in exemptions.split(",") if v.strip()]
    if not isinstance(exemptions, list):
        exemptions = []
    merged["mfa_exempt_usernames"] = sorted({str(v).strip() for v in exemptions if str(v).strip()})
    return merged


def _policy_from_json(raw: object) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        import json
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _merge_session_policy(policy: dict, overrides_raw: object) -> dict:
    overrides = _policy_from_json(overrides_raw)
    session_policy = overrides.get("session_policy") if isinstance(overrides, dict) else None
    if isinstance(session_policy, dict):
        return _normalise_session_policy(_deep_merge(policy, session_policy))
    return _normalise_session_policy(policy)


def _resolve_session_policy(
    db: Session,
    user: User | None = None,
    *,
    customer_id: str | None = None,
    site_id: str | None = None,
    camera_id: str | None = None,
) -> dict:
    policy = _normalise_session_policy({})
    try:
        defaults = db.query(ConfigDefaults).order_by(ConfigDefaults.id.asc()).first()
        if defaults and getattr(defaults, "session_policy", None):
            policy = _normalise_session_policy(_deep_merge(policy, _policy_from_json(defaults.session_policy)))
    except Exception as exc:
        log.warning("session_policy global resolver fejl: %s", exc)

    effective_customer_id = customer_id or getattr(user, "customer_id", None)
    site = None
    camera = None

    try:
        if camera_id:
            camera = db.query(Camera).filter_by(id=camera_id).first()
            if camera:
                site_id = site_id or camera.site_id
                effective_customer_id = effective_customer_id or camera.customer_id
        if site_id:
            site = db.query(Site).filter_by(id=site_id).first()
            if site:
                effective_customer_id = effective_customer_id or site.customer_id
        if effective_customer_id:
            customer = db.query(Customer).filter_by(id=effective_customer_id).first()
            if customer:
                policy = _merge_session_policy(policy, customer.config_overrides)
        if site:
            policy = _merge_session_policy(policy, site.config_overrides)
        if camera and camera.config:
            cam_cfg = _policy_from_json(camera.config)
            if isinstance(cam_cfg.get("session_policy"), dict):
                policy = _normalise_session_policy(_deep_merge(policy, cam_cfg["session_policy"]))
    except Exception as exc:
        log.warning("session_policy hierarki resolver fejl: %s", exc)
    return _normalise_session_policy(policy)


def _mfa_required_for_role(policy: dict, role: str | None) -> bool:
    if bool(policy.get("mfa_required")):
        return True
    return bool((policy.get("mfa_required_by_role") or {}).get(role or "", False))


def _mfa_required_for_user(db: Session, user: User | None, **scope) -> bool:
    if not user:
        return False
    policy = _resolve_session_policy(db, user, **scope)
    exempt = {str(v).strip().lower() for v in (policy.get("mfa_exempt_usernames") or [])}
    if user.username.strip().lower() in exempt:
        return False
    return _mfa_required_for_role(policy, user.role)


def _user_has_totp(user: User | None) -> bool:
    return bool(user and user.mfa_enabled and user.totp_secret)


def _user_has_partial_mfa(user: User | None) -> bool:
    return bool(user and (user.mfa_enabled or user.totp_secret) and not _user_has_totp(user))

# ── M-05: AgentPrincipal-håndhævelse (default-deny for agent-adgang til staging/prod) ──
#
# Baggrund: HANDOVER_LOG 2026-07-05 (Codex' oprindelige AgentPrincipal/AgentToken-forslag)
# + MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md §5 (permanent politik, uddybet 2026-07-06 med
# en SEPARAT, menneske-aktiveret break-glass-undtagelse — se Claude_Support_Access_Model_
# 2026-07-06.md — som IKKE går gennem denne mekanisme).
#
# Dette er "layer 2" i den oprindelige 5-trins byggerækkefølge (env-flag + hård afvisning),
# IKKE det fulde AgentPrincipal/AgentToken/AgentElevationGrant-skema (det er et separat,
# senere skridt hvis/når der reelt skal udstedes maskin-legitimation til agenter). Formålet
# her er en simpel, IKKE DB-konfigurerbar kodespærre: enhver bruger med role="agent" kan
# aldrig autentificeres — hverken ved login eller via en allerede udstedt cookie/JWT-session
# — når TIMELAPSE_ENV er staging/prod. "Ikke DB-konfigurerbar" er bevidst: det må ikke kunne
# slås fra ved en fejl i kunde-/site-/kamera-policy-hierarkiet (i modsætning til fx MFA-policy).
_AGENT_LOCKED_ENVIRONMENTS = {"staging", "prod", "production"}
_AGENT_ROLE = "agent"


def _agent_role_blocked_in_this_environment(role: str | None) -> bool:
    """True hvis en bruger med denne rolle IKKE må autentificeres i dette miljø (M-05)."""
    return (role or "").strip().lower() == _AGENT_ROLE and TIMELAPSE_ENV in _AGENT_LOCKED_ENVIRONMENTS


def _log_agent_lockdown_status():
    """Kører ved hvert opstart — samme mønster som `_warn_if_default_admin_password_active()`:
    gør håndhævelsens status synlig i SIEM ved hver eneste opstart, ikke kun i kildekoden."""
    if TIMELAPSE_ENV in _AGENT_LOCKED_ENVIRONMENTS:
        log.critical(
            "M-05 AgentPrincipal-håndhævelse AKTIV: TIMELAPSE_ENV='%s' — enhver bruger med "
            "role='agent' afvises hårdt ved login og ved eksisterende sessions (default-deny, "
            "jf. MILJOE_ARKITEKTUR_RD_STAGING_PROD_v1.md §5). Ikke konfigurerbar via DB-policy.",
            TIMELAPSE_ENV,
        )
    else:
        log.info(
            "M-05 AgentPrincipal-håndhævelse: TIMELAPSE_ENV='%s' — agent-rolle-spærren er kun "
            "aktiv i staging/prod, ikke i dette miljø.",
            TIMELAPSE_ENV,
        )


def _ensure_super_admin(db):
    """Opretter standard super_admin hvis ingen brugere findes."""
    from database import User
    if db.query(User).count() == 0:
        initial_password = resolve_initial_admin_password(
            TIMELAPSE_ENV, _AGENT_LOCKED_ENVIRONMENTS, log
        )
        admin = User(
            username      = "admin",
            email         = "admin@timelapse.local",
            password_hash = _hash_password(initial_password),
            role          = "super_admin",
            is_active     = True,
        )
        db.add(admin)
        db.commit()
        log.warning("Initial super_admin oprettet — skift den genererede adgangskode straks")

def _warn_if_default_admin_password_active(db):
    """Logger en VEDVARENDE advarsel (hvert opstart, ikke kun ved oprettelse) hvis en
    aktiv admin/super_admin-konto stadig bruger standard-passwordet 'changeme'.

    Baggrund (GO_LIVE_CHECKLIST_v10.md §C-03): "bekræft super_admin-password er
    ændret fra default" er en åben go-live-blokker. `_ensure_super_admin()` logger
    kun ÉN gang, ved selve oprettelsen — hvis den advarsel bliver overset, er der
    intet der minder om risikoen igen. Denne funktion kører ved hvert opstart og
    bruger `_verify_password()` (bcrypt) i stedet for en direkte hash-sammenligning,
    så den virker uanset salt. `log.critical()` her bliver samlet op af
    `headend/siem.py`s generiske log-baserede SIEM-pipeline (samme mønster som andre
    log-drevne sikkerhedshændelser i denne fil), så risikoen bliver synlig i SIEM
    indtil password rent faktisk skiftes — ikke kun i en opstartslog ingen læser.
    """
    from database import User
    try:
        admins = (
            db.query(User)
            .filter(User.role.in_(["admin", "super_admin"]), User.is_active == True)  # noqa: E712
            .all()
        )
    except Exception:
        log.exception("Kunne ikke tjekke for standard admin-password ved opstart")
        return
    for u in admins:
        try:
            if _verify_password("changeme", u.password_hash):
                log.critical(
                    "SIKKERHEDSADVARSEL: bruger '%s' (rolle=%s) bruger stadig standard-"
                    "passwordet 'changeme' — skift STRAKS via /api/auth/change-password "
                    "(GO_LIVE_CHECKLIST_v10.md §C-03)",
                    u.username, u.role,
                )
        except Exception:
            # En enkelt korrupt/ugyldig hash må aldrig stoppe tjekket af de øvrige brugere.
            continue

def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    """FastAPI dependency — returnerer current user fra cookie eller None."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = _decode_token(token)
    if not payload:
        return None
    user = db.query(User).filter_by(username=payload.get("sub"), is_active=True).first()
    # M-05 AgentPrincipal-håndhævelse — dækker sessions der allerede var udstedt FØR miljøet
    # blev spærret (fx en maskine der ændrer TIMELAPSE_ENV, eller en gendannet DB-kopi).
    # Centralt sted: alle cookie/JWT-autoriserede endpoints går gennem denne funktion.
    if user and _agent_role_blocked_in_this_environment(user.role):
        log.critical(
            "M-05 AgentPrincipal-håndhævelse: eksisterende session AFVIST for agent-rolle-"
            "bruger '%s' i miljø '%s' (token allerede udstedt, men miljøet er nu spærret).",
            user.username, TIMELAPSE_ENV,
        )
        return None
    return user

# Rollehierarki — højere roller inkluderer lavere rollers rettigheder
_ROLE_HIERARCHY = {
    "super_admin": {"super_admin", "admin", "operator", "viewer"},
    "admin":       {"admin", "operator", "viewer"},
    "operator":    {"operator", "viewer"},
    "viewer":      {"viewer"},
}

def require_role(*roles: str):
    """FastAPI dependency factory — kræver en af de angivne roller.
    Rollehierarki: super_admin > admin > operator > viewer.
    """
    def _check(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        allowed = _ROLE_HIERARCHY.get(user.role, {user.role})
        if not allowed.intersection(set(roles)):
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        if _mfa_required_for_user(db, user) and not _session_is_mfa_verified(_session_payload(request)):
            raise HTTPException(status_code=403, detail="MFA kræves for denne rolle")
        return user
    return Depends(_check)
