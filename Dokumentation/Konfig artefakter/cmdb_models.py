# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — cmdb_models.py (Headend)
# ───────────────────────────────────────────────────────────────────────────
# Version  : 1.0.0
# Dato     : 12. juni 2026
# ───────────────────────────────────────────────────────────────────────────
# CMDB + Opdaterings-pipeline datamodel.
#
# Tilføjer SQLAlchemy-modeller for hele opdateringsflowet:
#   InventoryItem    : installeret SW/OS/patch pr. platform (Headend + Edge)
#   AvailableUpdate  : opdagede tilgængelige opdateringer
#   UpdatePackage    : pakketeret opdatering klar til distribution
#   PackageTarget    : pr-enhed deploy-status for en pakke
#   ChangeRequest    : kunde-accept (mail / ticket-integration)
#   SbomDocument     : genereret SBOM pr. platform-snapshot
#
# VIGTIGT: Skrevet til PostgreSQL (produktion på Mac Mini). Genbruger Base
#          fra database.py, så create_tables() også opretter disse tabeller.
# ═══════════════════════════════════════════════════════════════════════════
"""TimeLapse Pro — CMDB datamodel (udvider database.py uden at ændre det)."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text, Index
)

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums (gemmes som String for PostgreSQL-portabilitet) ──────────────────

class Platform(str, enum.Enum):
    HEADEND = "headend"
    EDGE = "edge"


class ComponentKind(str, enum.Enum):
    OS = "os"
    OS_PACKAGE = "os_package"
    PYTHON_PACKAGE = "python_package"
    NPM_PACKAGE = "npm_package"
    APPLICATION = "application"
    FIRMWARE = "firmware"


class UpdateCategory(str, enum.Enum):
    OS_SECURITY = "os_security"
    OS_UPDATE = "os_update"
    APP_SECURITY = "app_security"
    APP_UPDATE = "app_update"
    TIMELAPSE = "timelapse"


class Criticality(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class PackageStatus(str, enum.Enum):
    DRAFT = "draft"
    TEST_AVAILABLE = "test_available"
    TESTING = "testing"
    TEST_PASSED = "test_passed"
    TEST_FAILED = "test_failed"
    STAGING_AVAILABLE = "staging_available"
    STAGING_PASSED = "staging_passed"
    PROD_AVAILABLE = "prod_available"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class TargetStatus(str, enum.Enum):
    PENDING = "pending"
    AWAITING_ACCEPT = "awaiting_accept"
    QUEUED = "queued"
    INSTALLING = "installing"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"


class ChangeRequestStatus(str, enum.Enum):
    PENDING = "pending"
    NOTIFIED = "notified"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    EXPIRED = "expired"


# Hvilke miljøer findes
ENVIRONMENTS = ("test", "staging", "production")


# ── Modeller ───────────────────────────────────────────────────────────────

class InventoryItem(Base):
    """Et installeret komponent på én platform-instans.

    Headend: platform_id = "headend" (singleton).
    Edge:    platform_id = device_id (TL-XXXX).
    Unik pr. (platform_id, kind, name).
    """
    __tablename__ = "cmdb_inventory"

    id            = Column(Integer, primary_key=True)
    platform      = Column(String(20), nullable=False, index=True)
    platform_id   = Column(String(60), nullable=False, index=True)
    kind          = Column(String(30), nullable=False)
    name          = Column(String(300), nullable=False)
    installed_ver = Column(String(120))
    available_ver = Column(String(120))
    category      = Column(String(30))
    criticality   = Column(String(20), default=Criticality.NONE.value)
    architecture  = Column(String(30))
    source        = Column(String(40))          # apt | pip | npm | git | brew
    cve_ids       = Column(Text)                # JSON-liste af relaterede CVE'er
    update_available = Column(Boolean, default=False, index=True)
    first_seen    = Column(DateTime, default=_utcnow)
    last_scanned  = Column(DateTime, default=_utcnow)
    extra         = Column(Text)                # JSON

Index("idx_inv_platform_kind", InventoryItem.platform_id, InventoryItem.kind)
Index("idx_inv_name", InventoryItem.platform_id, InventoryItem.name)


class SbomDocument(Base):
    """Genereret SBOM (CycloneDX JSON) pr. platform-snapshot."""
    __tablename__ = "cmdb_sbom"

    id           = Column(Integer, primary_key=True)
    platform     = Column(String(20), nullable=False)
    platform_id  = Column(String(60), nullable=False, index=True)
    format       = Column(String(30), default="cyclonedx-1.5")
    component_count = Column(Integer, default=0)
    sha256       = Column(String(64))
    generated_at = Column(DateTime, default=_utcnow, index=True)
    content      = Column(Text)                # fuld CycloneDX JSON


class UpdatePackage(Base):
    """En pakketeret opdatering klar til at gennemløbe pipelinen.

    En pakke samler 1..n komponenter af SAMME kategori (security/functional)
    og platform, så de kan godkendes og distribueres som én enhed.
    """
    __tablename__ = "cmdb_packages"

    id            = Column(Integer, primary_key=True)
    package_key   = Column(String(80), unique=True, index=True)   # fx "edge-os_security-20260612"
    title         = Column(String(300), nullable=False)
    platform      = Column(String(20), nullable=False)            # headend | edge
    category      = Column(String(30), nullable=False)            # UpdateCategory
    criticality   = Column(String(20), default=Criticality.MEDIUM.value)
    target_version = Column(String(120))                          # git-sha eller pakke-version
    from_version  = Column(String(120))
    components    = Column(Text)                # JSON: liste af {name, from, to, criticality}
    notes         = Column(Text)
    status        = Column(String(30), default=PackageStatus.DRAFT.value, index=True)
    test_plan_ref = Column(String(120))        # reference til testplan (fil/ID)
    # Pipeline-tidsstempler
    created_at    = Column(DateTime, default=_utcnow)
    test_at       = Column(DateTime)
    test_result_at= Column(DateTime)
    staging_at    = Column(DateTime)
    prod_at       = Column(DateTime)
    created_by    = Column(String(120))        # bruger-email
    approved_by   = Column(String(120))

Index("idx_pkg_status", UpdatePackage.status)


class PackageTarget(Base):
    """Pr-enhed (eller headend) deploy-status for en pakke."""
    __tablename__ = "cmdb_package_targets"

    id            = Column(Integer, primary_key=True)
    package_id    = Column(Integer, nullable=False, index=True)
    platform_id   = Column(String(60), nullable=False, index=True)  # "headend" | device_id
    environment   = Column(String(20), default="production")        # test|staging|production
    status        = Column(String(30), default=TargetStatus.PENDING.value, index=True)
    from_version  = Column(String(120))
    to_version    = Column(String(120))
    change_request_id = Column(Integer)        # FK til cmdb_change_requests (nullable)
    queued_at     = Column(DateTime)
    installed_at  = Column(DateTime)
    failed_reason = Column(Text)
    attempts      = Column(Integer, default=0)
    updated_at    = Column(DateTime, default=_utcnow)

Index("idx_tgt_pkg_dev", PackageTarget.package_id, PackageTarget.platform_id)


class ChangeRequest(Base):
    """Kunde-accept af en opdatering (mail / ticket-integration).

    Oprettes når en pakke skal til en enhed hvor auto-accept IKKE er slået
    til for den pågældende kategori i kunde/site/kamera-config.
    """
    __tablename__ = "cmdb_change_requests"

    id            = Column(Integer, primary_key=True)
    package_id    = Column(Integer, nullable=False, index=True)
    customer_id   = Column(String(36), index=True)
    site_id       = Column(String(36))
    platform_id   = Column(String(60))         # enhed CR'en gælder (kan være "all" for hele site)
    category      = Column(String(30))
    criticality   = Column(String(20))
    title         = Column(String(300))
    summary       = Column(Text)               # menneskelæsbar beskrivelse + komponentliste
    status        = Column(String(30), default=ChangeRequestStatus.PENDING.value, index=True)
    channel       = Column(String(30))         # email | webhook | manual | auto
    external_ref  = Column(String(200))        # ticket-ID fra kundens system
    token         = Column(String(80), index=True)  # signeret accept-link token
    requested_at  = Column(DateTime, default=_utcnow)
    notified_at   = Column(DateTime)
    decided_at    = Column(DateTime)
    decided_by    = Column(String(200))
    expires_at    = Column(DateTime)


class PipelineEvent(Base):
    """Audit-log for hele pipelinen (CRA/ISO 27001 sporbarhed)."""
    __tablename__ = "cmdb_pipeline_events"

    id          = Column(Integer, primary_key=True)
    package_id  = Column(Integer, index=True)
    platform_id = Column(String(60))
    actor       = Column(String(200))          # bruger-email | "system" | device_id
    action      = Column(String(80))           # created|test_available|promoted|deployed|...
    detail      = Column(Text)
    at          = Column(DateTime, default=_utcnow, index=True)
