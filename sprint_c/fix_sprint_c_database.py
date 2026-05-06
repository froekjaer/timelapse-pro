"""
TimeLapse Pro — Sprint C Database Migration
============================================
Tilføjer 5 nye tabeller til headend databasen:
  - users            (RBAC)
  - cameras          (logisk kamera, adskilt fra hardware)
  - device_assignments (historik: hvilken Pi kørte hvilket kamera)
  - ssh_tunnel_log   (audit af SSH tunnel sessioner)
  - pending_updates  (opdateringsstyring + godkendelse)

Kør fra roden af timelapse-pro repoet:
    python sprint_c/fix_sprint_c_database.py
"""

from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# Hvad vi tilføjer til headend/database.py
# ═══════════════════════════════════════════════════════════════════════════

DB_PATH = Path("headend/database.py")

assert DB_PATH.exists(), f"FEJL: {DB_PATH} ikke fundet — kør fra roden af repoet"

# ── Markør: indsæt efter Customer-klassen ────────────────────────────────
ANCHOR = '''class Customer(Base):
    __tablename__ = "customers"
    id               = Column(String(36), primary_key=True)
    name             = Column(String(200), nullable=False)
    contact_name     = Column(String(200))
    contact_email    = Column(String(200))
    contact_phone    = Column(String(50))
    address          = Column(String(500))
    notes'''

NEW_TABLES = '''

class User(Base):
    """RBAC brugere — super_admin, admin, operator, viewer."""
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True)
    username      = Column(String(100), unique=True, nullable=False, index=True)
    email         = Column(String(200), unique=True)
    password_hash = Column(String(200), nullable=False)
    role          = Column(String(50), default="viewer")   # super_admin|admin|operator|viewer
    customer_id   = Column(String(36))                     # null = adgang til alle kunder
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login    = Column(DateTime)


class Camera(Base):
    """Logisk kamera — adskilt fra fysisk Orange Pi hardware."""
    __tablename__ = "cameras"

    id            = Column(String(36), primary_key=True)   # UUID
    site_id       = Column(String(36), index=True)
    customer_id   = Column(String(36), index=True)
    camera_name   = Column(String(200), nullable=False)
    serial_number = Column(String(100))
    model         = Column(String(100))
    notes         = Column(Text)
    config        = Column(Text, default="{}")             # JSON camera-specifikke config overrides
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    retired_at    = Column(DateTime)                       # null = aktiv


class DeviceAssignment(Base):
    """Historik: hvilken Orange Pi kørte hvilket logisk kamera hvornår."""
    __tablename__ = "device_assignments"

    id            = Column(Integer, primary_key=True)
    device_id     = Column(String(50), nullable=False, index=True)   # MAC-baseret
    camera_id     = Column(String(36), nullable=False, index=True)   # → Camera.id
    assigned_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    unassigned_at = Column(DateTime)                                 # null = aktiv assignment
    assigned_by   = Column(String(100))                              # brugernavn
    notes         = Column(Text)


class SshTunnelLog(Base):
    """Audit log over SSH tunnel sessioner — SABSA Accountability."""
    __tablename__ = "ssh_tunnel_log"

    id           = Column(Integer, primary_key=True)
    device_id    = Column(String(50), nullable=False, index=True)
    event        = Column(String(50))    # connected|disconnected|failed|denied
    remote_port  = Column(Integer)
    local_port   = Column(Integer, default=22)
    initiated_by = Column(String(100))   # "edge_auto" | "admin:<username>"
    duration_s   = Column(Integer)       # udfyldes ved disconnect
    event_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    extra        = Column(Text)          # JSON: fejlbesked, IP osv.


class PendingUpdate(Base):
    """Opdateringer der afventer godkendelse eller deployment."""
    __tablename__ = "pending_updates"

    id          = Column(Integer, primary_key=True)
    update_type = Column(String(50))    # app_security|os_security|app_updates|os_updates
    version     = Column(String(100))
    description = Column(Text)
    severity    = Column(String(20))    # critical|high|medium|low
    scope       = Column(String(20))    # global|customer|site|device
    scope_id    = Column(String(36))    # customer_id, site_id eller device_id
    status      = Column(String(30), default="pending")
    # pending|approved|rejected|deployed|rolled_back
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    approved_at = Column(DateTime)
    approved_by = Column(String(100))
    deployed_at = Column(DateTime)
    rollback_at = Column(DateTime)

'''

# ── Verificer og anvend ───────────────────────────────────────────────────

content = DB_PATH.read_text()

GUARD = "class User(Base):"
if GUARD in content:
    print("✓ Sprint C tabeller allerede tilføjet — ingen ændringer")
    exit(0)

idx = content.find(ANCHOR)
assert idx != -1, \
    "FEJL: Kunne ikke finde Customer-klassen som ankerpunkt.\n" \
    "Tjek om database.py indeholder den forventede Customer-klasse."

# Indsæt de nye klasser lige FØR Customer (de er uafhængige)
insert_at = idx
content = content[:insert_at] + NEW_TABLES + content[insert_at:]

# ── Bump version ─────────────────────────────────────────────────────────
content = content.replace(
    "# Version  : 2.1.0",
    "# Version  : 3.0.0"
).replace(
    "# Dato     : 13. april 2026",
    "# Dato     : 06. maj 2026"
)

# Tilføj changelog-linje
content = content.replace(
    "#   2.1.0  13-apr-2026  Capture tabel udvidet med lokation/orientering:",
    "#   3.0.0  06-maj-2026  Sprint C: User, Camera, DeviceAssignment,\n"
    "#                       SshTunnelLog, PendingUpdate tabeller\n"
    "#   2.1.0  13-apr-2026  Capture tabel udvidet med lokation/orientering:"
)

DB_PATH.write_text(content)
print(f"✓ {DB_PATH} opdateret til v3.0.0")
print("  Tilføjede tabeller: User, Camera, DeviceAssignment, SshTunnelLog, PendingUpdate")

# ── Opdater database-import i main.py ────────────────────────────────────
MAIN_PATH = Path("headend/main.py")
if MAIN_PATH.exists():
    main_content = MAIN_PATH.read_text()
    old_import = "from database import (\n    Capture, Customer, ConfigDefaults, Device, Diagnostic, Event, Settings, Site,"
    new_import = "from database import (\n    Capture, Camera, Customer, ConfigDefaults, Device, DeviceAssignment,\n    Diagnostic, Event, PendingUpdate, Settings, Site, SshTunnelLog, User,"
    if old_import in main_content and "Camera," not in main_content:
        main_content = main_content.replace(old_import, new_import)
        MAIN_PATH.write_text(main_content)
        print(f"✓ {MAIN_PATH} import opdateret")
    else:
        print(f"  {MAIN_PATH} import allerede OK")

print("\nHusk: git add headend/database.py headend/main.py")
print("Næste: kør fix_sprint_c_auth.py for RBAC endpoints")
