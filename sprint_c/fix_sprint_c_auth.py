"""
TimeLapse Pro — Sprint C: RBAC Auth Endpoints
==============================================
Tilføjer til headend/main.py:
  - JWT login/refresh/logout endpoints
  - require_role() dependency decorator
  - User CRUD endpoints
  - Første super_admin bruger oprettes automatisk

Krav: python-jose, bcrypt, passlib allerede i venv (verificeret)

Kør fra roden af timelapse-pro repoet:
    python sprint_c/fix_sprint_c_auth.py
"""

from pathlib import Path

MAIN_PATH = Path("headend/main.py")
assert MAIN_PATH.exists(), "FEJL: Kør fra roden af repoet"

# ── Guard ─────────────────────────────────────────────────────────────────
GUARD = "# ── AUTH / RBAC ─"
content = MAIN_PATH.read_text()
if GUARD in content:
    print("✓ Auth endpoints allerede tilføjet — ingen ændringer")
    exit(0)

# ── Nyt indhold der indsættes efter imports-sektionen ────────────────────
AUTH_IMPORTS = '''
# ── Auth imports (Sprint C) ───────────────────────────────────────────────
from jose import JWTError, jwt as _jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Security
import secrets as _secrets

_pwd_ctx      = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

JWT_SECRET    = os.getenv("JWT_SECRET", _secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_H  = 12   # access token levetid

'''

# ── Auth helper-funktioner og endpoints ──────────────────────────────────
AUTH_SECTION = '''
# ═══════════════════════════════════════════════════════════════════════════
# ── AUTH / RBAC ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════

def _hash_password(pw: str) -> str:
    return _pwd_ctx.hash(pw)

def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)

def _create_token(data: dict, expire_hours: int = JWT_EXPIRE_H) -> str:
    from datetime import timedelta
    payload = data.copy()
    payload["exp"] = now_utc() + timedelta(hours=expire_hours)
    return _jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def _decode_token(token: str) -> dict | None:
    try:
        return _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None

def _ensure_super_admin(db):
    """Opretter standard super_admin hvis ingen brugere findes."""
    from database import User
    if db.query(User).count() == 0:
        admin = User(
            username      = "admin",
            email         = "admin@timelapse.local",
            password_hash = _hash_password("changeme"),
            role          = "super_admin",
            is_active     = True,
        )
        db.add(admin)
        db.commit()
        log.warning("Standard super_admin oprettet — SKIFT PASSWORD STRAKS via /api/auth/change-password")

def get_current_user(
    token: str = Security(_oauth2_scheme),
    db: Session = Depends(get_db)
):
    """FastAPI dependency — returnerer current user eller None."""
    if not token:
        return None
    payload = _decode_token(token)
    if not payload:
        return None
    from database import User
    user = db.query(User).filter_by(username=payload.get("sub"), is_active=True).first()
    return user

def require_role(*roles: str):
    """FastAPI dependency factory — kræver en af de angivne roller."""
    def _check(user=Depends(get_current_user)):
        if user is None:
            raise HTTPException(status_code=401, detail="Ikke autentificeret")
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Kræver rolle: {', '.join(roles)}")
        return user
    return Depends(_check)


# ── Auth models ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class UserCreateRequest(BaseModel):
    username:    str
    email:       Optional[str] = None
    password:    str
    role:        str = "viewer"
    customer_id: Optional[str] = None

class UserUpdateRequest(BaseModel):
    email:       Optional[str] = None
    role:        Optional[str] = None
    customer_id: Optional[str] = None
    is_active:   Optional[bool] = None


# ── Auth endpoints ────────────────────────────────────────────────────────

@app.on_event("startup")
def _startup_ensure_admin():
    """Ensure super_admin exists on startup."""
    db = next(get_db())
    try:
        _ensure_super_admin(db)
    finally:
        db.close()

@app.post("/api/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login — returnerer JWT access token."""
    from database import User
    user = db.query(User).filter_by(username=req.username, is_active=True).first()
    if not user or not _verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Forkert brugernavn eller adgangskode")
    user.last_login = now_utc()
    db.commit()
    token = _create_token({"sub": user.username, "role": user.role, "cid": user.customer_id})
    log.info("Login: %s (%s)", user.username, user.role)
    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user.role,
        "username":     user.username,
        "expires_in":   JWT_EXPIRE_H * 3600,
    }

@app.post("/api/auth/logout")
def logout():
    """Logout — klienten sletter token lokalt."""
    return {"ok": True}

@app.post("/api/auth/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Skift adgangskode for den indloggede bruger."""
    if current_user is None:
        raise HTTPException(status_code=401)
    if not _verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Forkert nuværende adgangskode")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Adgangskode skal være mindst 8 tegn")
    current_user.password_hash = _hash_password(req.new_password)
    db.commit()
    log.info("Adgangskode skiftet: %s", current_user.username)
    return {"ok": True}

@app.get("/api/auth/me")
def me(current_user=Depends(get_current_user)):
    """Returnerer den aktuelle brugers info."""
    if current_user is None:
        raise HTTPException(status_code=401)
    return {
        "username":    current_user.username,
        "email":       current_user.email,
        "role":        current_user.role,
        "customer_id": current_user.customer_id,
    }


# ── User CRUD (kun super_admin) ───────────────────────────────────────────

@app.get("/api/admin/users")
def list_users(
    _user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    from database import User
    users = db.query(User).order_by(User.username).all()
    return [
        {
            "id":          u.id,
            "username":    u.username,
            "email":       u.email,
            "role":        u.role,
            "customer_id": u.customer_id,
            "is_active":   u.is_active,
            "created_at":  u.created_at.isoformat() if u.created_at else None,
            "last_login":  u.last_login.isoformat() if u.last_login else None,
        }
        for u in users
    ]

@app.post("/api/admin/users")
def create_user(
    req: UserCreateRequest,
    _user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    from database import User
    if db.query(User).filter_by(username=req.username).first():
        raise HTTPException(status_code=400, detail="Brugernavn findes allerede")
    if req.role not in ("super_admin", "admin", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="Ugyldig rolle")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Adgangskode skal være mindst 8 tegn")
    u = User(
        username      = req.username,
        email         = req.email,
        password_hash = _hash_password(req.password),
        role          = req.role,
        customer_id   = req.customer_id,
    )
    db.add(u); db.commit(); db.refresh(u)
    log.info("Bruger oprettet: %s (%s)", u.username, u.role)
    return {"id": u.id, "username": u.username}

@app.put("/api/admin/users/{user_id}")
def update_user(
    user_id: int,
    req: UserUpdateRequest,
    _user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    from database import User
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(status_code=404)
    if req.role and req.role not in ("super_admin", "admin", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="Ugyldig rolle")
    for field in ["email", "role", "customer_id", "is_active"]:
        val = getattr(req, field)
        if val is not None:
            setattr(u, field, val)
    db.commit()
    return {"ok": True}

@app.delete("/api/admin/users/{user_id}")
def delete_user(
    user_id: int,
    current_user=require_role("super_admin"),
    db: Session = Depends(get_db)
):
    from database import User
    u = db.query(User).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(status_code=404)
    if u.username == "admin" and u.role == "super_admin":
        raise HTTPException(status_code=400, detail="Kan ikke slette primær super_admin")
    db.delete(u); db.commit()
    return {"ok": True}

'''

# ── Anvend patch ──────────────────────────────────────────────────────────

# 1. Tilføj imports efter eksisterende os-import
OLD_OS_IMPORT = "import os, tempfile"
assert OLD_OS_IMPORT in content, "FEJL: Kunne ikke finde 'import os, tempfile' som ankerpunkt"
content = content.replace(OLD_OS_IMPORT, OLD_OS_IMPORT + AUTH_IMPORTS, 1)

# 2. Indsæt auth-sektionen før Sprint A
SPRINT_A_MARKER = "# ═══════════════════════════════════════════════════════════════════════════\n# Sprint A — Customer / Site / Device CRUD"
assert SPRINT_A_MARKER in content, "FEJL: Kunne ikke finde Sprint A markøren"
content = content.replace(SPRINT_A_MARKER, AUTH_SECTION + "\n" + SPRINT_A_MARKER, 1)

# 3. Bump version
content = content.replace(
    "# Version  : 2.7.0",
    "# Version  : 3.0.0"
)
content = content.replace(
    "#   2.7.0  13-apr-2026  Timelapse video rendering via FFmpeg",
    "#   3.0.0  06-maj-2026  Sprint C: RBAC, JWT auth, User CRUD,\n"
    "#                       Camera/Pi-kobling, SSH tunnel, Opdateringsstyring\n"
    "#   2.7.0  13-apr-2026  Timelapse video rendering via FFmpeg"
)

MAIN_PATH.write_text(content)
print(f"✓ {MAIN_PATH} opdateret med RBAC auth endpoints")
print("  Standard login: admin / changeme — SKIFT STRAKS!")
print("\nHusk: git add headend/main.py")
print("Næste: kør fix_sprint_c_ssh_endpoints.py")
