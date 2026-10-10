# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — technician_keys.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
SSH public key management for field-role users (installer/technician).

Montér i main.py:
    from technician_keys import router as technician_keys_router
    app.include_router(technician_keys_router, prefix="/api/admin")

Endpoints:
    GET    /api/admin/users/{user_id}/ssh-keys
    POST   /api/admin/users/{user_id}/ssh-keys
    DELETE /api/admin/users/{user_id}/ssh-keys/{key_id}

First slice of the break-glass/RBAC redesign (2026-08-19, per Peter): a
technician's personal SSH public key, not a single shared operational key,
is what gets replicated to edge devices — see headend/edge_sync.py (reads
these) and edge/agent.py::_run_sync() (writes the local cache sshd's
AuthorizedKeysCommand reads). Lives on its own APIRouter, not a direct
@app route in main.py, per tests/test_architecture_ratchet.py.

Public keys are, by definition, public — this module never handles or
stores anything secret. Revocation is soft (revoked_at timestamp), not a
hard delete, so a device's already-cached copy is provably auditable
against what was actually authorized at any point in time.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db, Site, User, UserSSHKey
from auth import get_current_user
from tenant_scope import _allowed_customer_ids, user_customer_ids

log = logging.getLogger(__name__)

router = APIRouter(tags=["Technician Keys"])


def migrate_field_role_column(engine) -> None:
    """Replace users.on_site_service (boolean) with users.field_role (tag).
    Additive migration for existing PostgreSQL data, called once from
    main.py::startup(). Backfills existing TRUE values to 'technician', then
    drops the old column in the same pass — deliberately not left as an
    orphaned column once superseded (see FIND-DEVICES-PLAINTEXT-SSH-KEY-COLUMN
    for why that's a hard rule now, not just a preference)."""
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN field_role VARCHAR(20) NOT NULL DEFAULT 'none'"
                ))
                conn.commit()
                log.info("DB migration: users.field_role tilføjet")
            except Exception:
                pass
            try:
                conn.execute(text(
                    "UPDATE users SET field_role = 'technician' WHERE on_site_service = TRUE AND field_role = 'none'"
                ))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE users DROP COLUMN on_site_service"))
                conn.commit()
                log.info("DB migration: users.on_site_service fjernet (erstattet af field_role)")
            except Exception:
                pass
    except Exception as exc:
        log.warning("DB migration users.field_role fejl: %s", exc)


def migrate_user_ssh_keys_table(engine) -> None:
    """Create the user_ssh_keys table if missing. Called once from
    main.py::startup(), alongside its other additive DB migrations."""
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_ssh_keys (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        public_key TEXT NOT NULL,
                        label VARCHAR(200),
                        created_at TIMESTAMP,
                        created_by VARCHAR(100),
                        revoked_at TIMESTAMP
                    )
                """))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_user_ssh_keys_user_id ON user_ssh_keys (user_id)"
                ))
                conn.commit()
            except Exception:
                pass
    except Exception as exc:
        log.warning("DB migration user_ssh_keys fejl: %s", exc)


def drop_orphaned_device_credential_columns(engine) -> None:
    """Remove devices.{ssh_private_key,bt_totp_secret,factory_totp_disabled,
    shared_ssh_key_disabled} — FIND-DEVICES-PLAINTEXT-SSH-KEY-COLUMN (2026-08-19):
    devices.ssh_private_key held real, unencrypted OpenSSH private keys for
    2 production devices; none of these 4 columns were ever read or written
    by any code. Leftovers from a third, abandoned "give the device its own
    credentials" design — never the same as the merged BreakGlassAccount or
    the closed/unmerged PR #9. Peter decided 2026-08-21: consolidate on
    BreakGlassAccount (password) + RBAC technician keys (#79/#95); this third
    variant is retired, not developed further. Confirmed the same night that
    the exposed keys don't match anything actually trusted on either device
    today (direct SSH attempts refused) — this is cleanup of exposed-but-
    inert secret material, not revocation of live access."""
    try:
        with engine.connect() as conn:
            for column in (
                "ssh_private_key", "bt_totp_secret",
                "factory_totp_disabled", "shared_ssh_key_disabled",
            ):
                try:
                    conn.execute(text(f"ALTER TABLE devices DROP COLUMN IF EXISTS {column}"))
                    conn.commit()
                except Exception:
                    pass
        log.info("DB migration: orphaned devices credential columns fjernet")
    except Exception as exc:
        log.warning("DB migration orphaned devices-kolonner fejl: %s", exc)

_ALLOWED_KEY_PREFIXES = ("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")


async def _require_self_or_admin(user_id: int, request: Request, db: Session = Depends(get_db)):
    """A user may manage their own keys; admin/super_admin may manage anyone's.
    get_current_user comes from auth.py at module scope (2026-08-26) — auth.py
    doesn't depend on main.py, so this is no longer a circular-import concern.
    """
    current_user = get_current_user(request, db)
    if current_user is None:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    if current_user.id != user_id and not _may_manage_user_keys(db, current_user, user_id):
        raise HTTPException(status_code=403, detail="Kan kun administrere egne SSH-nøgler")
    return current_user


def _may_manage_user_keys(db: Session, actor, user_id: int) -> bool:
    """super_admin: anyone. admin: only users who are wholly inside the
    admin's own customers (never a super_admin, never a user without
    customers) — these keys are replicated to Edges."""
    if getattr(actor, "role", None) == "super_admin":
        return True
    if getattr(actor, "role", None) != "admin":
        return False
    target = db.query(User).filter_by(id=user_id).first()
    if target is None or target.role == "super_admin":
        return False
    allowed = _allowed_customer_ids(db, actor) or set()
    target_customers = user_customer_ids(target)
    return bool(target_customers) and target_customers <= allowed


class SSHKeyCreateRequest(BaseModel):
    public_key: str
    label: str | None = None


def _validate_public_key(raw: str) -> str:
    key = raw.strip()
    if not key.startswith(_ALLOWED_KEY_PREFIXES):
        raise HTTPException(
            status_code=400,
            detail="Ugyldig SSH public key — skal starte med ssh-ed25519, ssh-rsa eller ecdsa-sha2-",
        )
    if "PRIVATE KEY" in key.upper():
        raise HTTPException(status_code=400, detail="Dette ligner en privat nøgle, ikke en public key")
    return key


@router.get("/users/{user_id}/ssh-keys")
def list_user_ssh_keys(
    user_id: int,
    current_user=Depends(_require_self_or_admin),
    db: Session = Depends(get_db),
):
    keys = db.query(UserSSHKey).filter_by(user_id=user_id).order_by(UserSSHKey.created_at.desc()).all()
    return [
        {
            "id": k.id,
            "label": k.label,
            "public_key": k.public_key,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "created_by": k.created_by,
            "revoked_at": k.revoked_at.isoformat() if k.revoked_at else None,
        }
        for k in keys
    ]


@router.post("/users/{user_id}/ssh-keys")
def add_user_ssh_key(
    user_id: int,
    req: SSHKeyCreateRequest,
    current_user=Depends(_require_self_or_admin),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Bruger ikke fundet")
    public_key = _validate_public_key(req.public_key)
    key = UserSSHKey(
        user_id=user_id,
        public_key=public_key,
        label=(req.label or "").strip() or None,
        created_at=datetime.now(timezone.utc),
        created_by=current_user.username,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return {"id": key.id}


def resolve_authorized_technician_keys(db: Session, device) -> list[dict]:
    """Every currently-valid public key for a field-role user (installer or
    technician) with access to this device's customer, for inclusion in the
    consolidated sync-poll response (headend/edge_sync.py). Central role model
    (tenant_scope, 2026-10-10): super_admin field staff are included for every
    device; everyone else only for devices of a customer they are attached to
    (device or site customer). A non-super_admin user without customers gets
    no Edge — previously such a user counted as platform-wide field staff.

    Returns audit-labelled entries, not per-user Linux accounts — the edge
    side authenticates all of these against a single shared functional
    account (see Dokumentation/HANDOVER_LOG.md 2026-08-19 for why: only the
    break-glass account is meant to be a real local Linux account).
    """
    device_customers = {str(c) for c in (getattr(device, "customer_id", None),) if c}
    site_id = getattr(device, "site_id", None)
    if site_id:
        site = db.query(Site).filter_by(id=site_id).first()
        if site and site.customer_id:
            device_customers.add(str(site.customer_id))
    users = (
        db.query(User)
        .filter(User.field_role.in_(("installer", "technician")))
        .filter(User.is_active.is_(True))
        .all()
    )
    entries: list[dict] = []
    for user in users:
        # Central role model: super_admin everywhere; anyone else only on
        # devices of a customer they are attached to (none → no Edge).
        allowed = _allowed_customer_ids(db, user)
        if allowed is not None and not (allowed & device_customers):
            continue
        keys = (
            db.query(UserSSHKey)
            .filter_by(user_id=user.id)
            .filter(UserSSHKey.revoked_at.is_(None))
            .all()
        )
        for key in keys:
            entries.append({
                "public_key": key.public_key,
                "identity": f"{user.username}:{key.label or key.id}",
                "field_role": user.field_role,
            })
    return entries


@router.delete("/users/{user_id}/ssh-keys/{key_id}")
def revoke_user_ssh_key(
    user_id: int,
    key_id: int,
    current_user=Depends(_require_self_or_admin),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    key = db.query(UserSSHKey).filter_by(id=key_id, user_id=user_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Nøgle ikke fundet")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return {"ok": True}
