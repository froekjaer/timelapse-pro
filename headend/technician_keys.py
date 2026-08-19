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

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, User, UserSSHKey

router = APIRouter(tags=["Technician Keys"])

_ALLOWED_KEY_PREFIXES = ("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")


async def _require_self_or_admin(user_id: int, request: Request, db: Session = Depends(get_db)):
    """A user may manage their own keys; admin/super_admin may manage anyone's.
    Lazy import: main.py imports this module at load time, so a module-scope
    import of main here would be circular. Same idiom as edge_sync.py /
    local_access.py.
    """
    from main import get_current_user

    current_user = get_current_user(request, db)
    if current_user is None:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    if current_user.id != user_id and current_user.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Kan kun administrere egne SSH-nøgler")
    return current_user


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
    consolidated sync-poll response (headend/edge_sync.py). Global field-role
    users (no customer_id — platform-wide field staff) are included for every
    device; customer-scoped users only for devices under that same customer.

    Returns audit-labelled entries, not per-user Linux accounts — the edge
    side authenticates all of these against a single shared functional
    account (see Dokumentation/HANDOVER_LOG.md 2026-08-19 for why: only the
    break-glass account is meant to be a real local Linux account).
    """
    device_customer_id = getattr(device, "customer_id", None)
    users = (
        db.query(User)
        .filter(User.field_role.in_(("installer", "technician")))
        .filter(User.is_active.is_(True))
        .all()
    )
    entries: list[dict] = []
    for user in users:
        if user.customer_id and device_customer_id and str(user.customer_id) != str(device_customer_id):
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
