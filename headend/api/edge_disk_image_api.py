# ═══════════════════════════════════════════════════════════════════════════
# TimeLapse Pro — edge_disk_image_api.py (Headend)
# ═══════════════════════════════════════════════════════════════════════════
"""
Edge disk-image build + WiFi-injection pipeline.

Montér i main.py:
    from api.edge_disk_image_api import router as edge_disk_image_router
    app.include_router(edge_disk_image_router)

Endpoints:
    POST   /api/admin/edge-provisioning/build-disk-image
    GET    /api/admin/edge-provisioning/disk-image-status
    GET    /api/admin/edge-provisioning/targets
    GET    /api/admin/edge-provisioning/disk-images
    GET    /api/admin/edge-provisioning/disk-image-download/{artifact_id}
    DELETE /api/admin/edge-provisioning/disk-images/{artifact_id}
    POST   /api/admin/edge-provisioning/inject-wifi
    GET    /api/admin/edge-provisioning/wifi-inject-status

Extracted from main.py (2026-08-26, Phase 1 of the main.py modularization
plan — see /Users/peter/.claude/plans/twinkling-toasting-treehouse.md).
This was the cheapest first win: main.py already had a local
`_edge_image_admin_router = APIRouter()` for the DELETE route (routes on a
locally-instantiated APIRouter aren't counted by
tests/test_architecture_ratchet.py's regex, only `@app.*` decorators are —
so that one route was already "extracted in spirit"), and the rest of this
domain's routes/state/background-thread functions sat right next to it,
under main.py's own "# ── Edge disk image build pipeline ──" section header.

Two adjacent routes were deliberately NOT moved here despite sharing the
`/api/admin/edge-provisioning/` path prefix, because their actual code
coupling points elsewhere:
  - POST .../prepare (bootstrap-token generation, bootstrap.yaml) is more
    coupled to the device-enrollment/bootstrap domain — a separate,
    not-yet-extracted Phase 2 domain in the plan.
  - POST .../build-image (edge_bootstrap_image manifest) calls
    _canonical_json/_sha256_text/_sign_payload/_artifact_to_dict — core
    machinery of the much larger Updates/artifacts/releases domain
    (Phase 3, last in the plan, split into two PRs). Moving it here would
    have meant either duplicating that machinery or reaching back into
    main.py for it — same circular-import problem this whole plan exists
    to retire, not worth it for one route.

require_role/get_current_user now come from auth.py at module scope
(Phase 0) — no lazy import needed for auth. A few genuinely main.py-wide
utilities this domain still needs (_get_setting, _repo_root,
_headend_api_url, _git_text — each used broadly across main.py, not
specific to this domain) are still lazy-imported per function, matching
the same idiom already used by importer.py and headend_generator_api.py
for their own main.py-specific dependencies.
"""
from __future__ import annotations

import json
import logging
import os
import threading as _threading
from pathlib import Path
from typing import Optional

import edge_provisioning_security as _edge_provisioning
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import DeviceAssignment, Event, SessionLocal, UpdateArtifact, get_db, now_utc
from auth import require_role

log = logging.getLogger("headend")

router = APIRouter(tags=["Edge Provisioning"])


# ── Edge disk image build pipeline ────────────────────────────────────────────

_edge_disk_build_status: dict = {
    "running": False, "progress": [], "error": None, "result": None,
}
_edge_disk_build_lock = _threading.Lock()


class DiskImageBuildRequest(BaseModel):
    target: str = "orangepi4pro"
    mode: str = "rootfs"          # "rootfs" | "flashable"
    bootstrap_token: str = ""     # kun til "flashable" mode
    wifi_ssid: str = ""           # bages ind i image (valgfrit)
    wifi_password: str = ""       # WiFi adgangskode
    wifi_country: str = "DK"      # WiFi landekode
    camera_id: Optional[str] = None  # UUID til Camera → SSH keys + tunnel port hentes fra DB
    expected_device_id: str = ""  # fysisk Edge-ID fra mærkat/QR, bundet til lokal TLS-identitet
    interactive_shell_enabled: bool = False  # Explicit R&D/local technician shell bootstrap policy


def _edge_image_storage_dir(*, create: bool = True) -> Path:
    from main import _get_setting, _repo_root
    configured = os.getenv("TIMELAPSE_EDGE_IMAGE_DIR")
    if not configured:
        db = SessionLocal()
        try:
            configured = _get_setting(db, "edge_image_artifact_dir", "")
            from storage_registry import EDGE_ARTIFACTS, resolve_storage
            configured = str(resolve_storage(db, EDGE_ARTIFACTS, configured or None, writable=True))
        finally:
            db.close()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        Path("/Volumes/data-fast/peter-home/timelapse-artifacts/edge-images"),
        Path("/Volumes/data-fast/backup/timelapse-artifacts/edge-images"),
        _repo_root() / "headend" / "exports" / "edge-images",
    ])

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            if not create:
                return candidate
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return candidate
        except Exception as exc:
            last_error = exc
            log.warning("Edge image storage %s er ikke skrivbar: %s", candidate, exc)
    raise RuntimeError(f"Ingen skrivbar Edge image artifact-mappe fundet: {last_error}")


def _edge_image_manifest_index(storage_dir: Path) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for manifest_path in storage_dir.glob("*.manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        image = manifest.get("image") if isinstance(manifest, dict) else None
        filename = image.get("filename") if isinstance(image, dict) else None
        if filename:
            index[str(filename)] = manifest
        artifact_id = manifest.get("artifact_id") if isinstance(manifest, dict) else None
        if artifact_id:
            index[str(artifact_id)] = manifest
    return index


def _edge_image_file_entries(storage_dir: Path) -> list[dict]:
    manifests = _edge_image_manifest_index(storage_dir)
    entries: list[dict] = []
    for file_path in sorted(
        list(storage_dir.glob("*.img.gz")) + list(storage_dir.glob("*.rootfs.tar.gz")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        manifest = manifests.get(file_path.name) or {}
        artifact_id = str(manifest.get("artifact_id") or file_path.name)
        image_meta = manifest.get("image") if isinstance(manifest.get("image"), dict) else {}
        created_at = manifest.get("created_at")
        artifact_type = str(
            manifest.get("artifact_type")
            or ("flashable_disk_image" if file_path.name.endswith(".img.gz") else "edge_disk_image")
        )
        entries.append({
            "artifact_id": artifact_id,
            "filename": file_path.name,
            "artifact_type": artifact_type,
            "size_bytes": int(image_meta.get("size_bytes") or file_path.stat().st_size),
            "sha256": image_meta.get("sha256"),
            "created_at": created_at,
            "exists_on_disk": True,
            "source": "filesystem",
            "storage_path": str(file_path),
        })
    return entries


def _resolve_edge_image_path(artifact_id: str, db: Session) -> tuple[Path, str]:
    artifact = db.query(UpdateArtifact).filter(
        UpdateArtifact.artifact_id == artifact_id,
        UpdateArtifact.artifact_type.in_(["edge_disk_image", "flashable_disk_image"]),
    ).first()
    if artifact:
        if not artifact.storage_path or not os.path.exists(artifact.storage_path):
            raise HTTPException(status_code=410, detail="Image-fil ikke tilgængelig (måske slettet fra disk)")
        return Path(artifact.storage_path), artifact.filename or f"{artifact_id}.img.gz"

    storage_dir = _edge_image_storage_dir()
    manifests = _edge_image_manifest_index(storage_dir)
    for entry in _edge_image_file_entries(storage_dir):
        if artifact_id in {entry["artifact_id"], entry["filename"]}:
            return Path(entry["storage_path"]), entry["filename"]
    manifest = manifests.get(artifact_id)
    if manifest and isinstance(manifest.get("image"), dict):
        filename = manifest["image"].get("filename")
        if filename:
            candidate = storage_dir / str(filename)
            if candidate.exists():
                return candidate, str(filename)
    raise HTTPException(status_code=404, detail="Artifact ikke fundet")


def _run_edge_disk_image_build(
    headend_url: str,
    gpg_key_id: str | None,
    output_dir: str,
    db_factory,
    target: str = "orangepi4pro",
    mode: str = "rootfs",
    bootstrap_token: str = "",
    wifi_ssid: str = "",
    wifi_password: str = "",
    wifi_country: str = "DK",
    camera_id: Optional[str] = None,
    expected_device_id: str = "",
    interactive_shell_enabled: bool = False,
) -> None:
    """Background thread: bygger edge disk image og registrerer artifact.

    mode="rootfs"    → kun Docker buildx → rootfs.tar.gz (eksisterende adfærd)
    mode="flashable" → rootfs + injection → flashbart .img.gz klar til SD/NVMe
    """
    from main import _repo_root, _git_text
    global _edge_disk_build_status
    try:
        from headend.tools.build_edge_disk_image import build_edge_image
    except ImportError:
        import sys
        sys.path.insert(0, str(_repo_root() / "headend"))
        from tools.build_edge_disk_image import build_edge_image  # type: ignore

    def progress(msg: str) -> None:
        _edge_disk_build_status["progress"].append(msg)
        log.info("[edge-image-build] %s", msg)

    try:
        # ── Trin 1: Byg rootfs via Docker buildx ──────────────────────────
        result = build_edge_image(
            target=target,
            headend_url=headend_url,
            gpg_key_id=gpg_key_id,
            progress_cb=progress,
            repo_root=str(_repo_root()),
            output_dir=output_dir,
        )

        # ── Trin 2 (valgfri): Injectér i base-image → flashbar .img.gz ───
        if mode == "flashable":
            # Brug importlib.reload for at sikre vi altid henter den nyeste
            # version af inject_edge_image.py fra disk — ikke en cachet version
            # fra sys.modules (som kan være gammel hvis headend kører --reload).
            import importlib
            try:
                import headend.tools.inject_edge_image as _inj_mod
                importlib.reload(_inj_mod)
                inject_edge_image = _inj_mod.inject_edge_image
            except (ImportError, ModuleNotFoundError):
                import sys
                sys.path.insert(0, str(_repo_root() / "headend"))
                import tools.inject_edge_image as _inj_mod  # type: ignore
                importlib.reload(_inj_mod)
                inject_edge_image = _inj_mod.inject_edge_image

            progress(f"\n💉 Mode=flashable — starter image injection...")

            # ── Hent ikke-private service metadata; Edge private keys forbliver lokale. ──
            _headend_ssh_pubkey = ""
            _ssh_tunnel_port    = 0
            _bt_totp_secret = ""
            _bt_totp_sid = ""
            _local_tls: dict[str, str] = {}
            if not camera_id:
                raise RuntimeError("Flashbart Edge-image kræver en valgt kameralokation for unik lokal adgang")
            try:
                import pyotp as _pyotp
                from database import Camera as _Camera
                _db_ssh = db_factory()
                try:
                    _cam = _db_ssh.query(_Camera).filter_by(id=camera_id).first()
                    if not _cam:
                        raise RuntimeError(f"Kameralokation findes ikke: {camera_id}")
                    _ssh_tunnel_port = int(getattr(_cam, "reverse_tunnel_port", 0) or 0)
                    _cam_name = getattr(_cam, "camera_name", camera_id)
                    if not getattr(_cam, "bt_totp_secret", None):
                        _cam.bt_totp_secret = _pyotp.random_base32()
                        _cam.bt_totp_sid = f"camera-{str(camera_id)[:8]}"
                        _db_ssh.commit()
                        progress(f"   🔐 Kamera '{_cam_name}': unik lokal nødadgang oprettet")
                    _bt_totp_secret = _cam.bt_totp_secret
                    _bt_totp_sid = _cam.bt_totp_sid or f"camera-{str(camera_id)[:8]}"
                    _assigned = _db_ssh.query(DeviceAssignment).filter(
                        DeviceAssignment.camera_id == camera_id,
                        DeviceAssignment.unassigned_at.is_(None),
                    ).order_by(DeviceAssignment.assigned_at.desc()).first()
                    _resolved_device_id = (expected_device_id or (_assigned.device_id if _assigned else "")).strip()
                    if not _resolved_device_id:
                        raise RuntimeError("Flashbart image kræver fysisk Edge-ID fra mærkat eller QR-kode")
                    try:
                        from headend.services.edge_local_pki import issue_local_edge_server_certificate
                    except (ImportError, ModuleNotFoundError):
                        from services.edge_local_pki import issue_local_edge_server_certificate
                    _local_tls = issue_local_edge_server_certificate(_resolved_device_id)
                    progress(f"   🔐 Lokal TLS udstedt: {_local_tls['hostname']} (Edge-ID {_resolved_device_id})")
                    progress(f"   🔑 Kamera '{_cam_name}': Edge-ejet SSH identity; Headend injicerer ingen privat nøgle")
                finally:
                    _db_ssh.close()
            except Exception as _e:
                raise RuntimeError(f"Kunne ikke provisionere kameraets lokale adgang: {_e}") from _e

            # Headend public key fra ~/.ssh/timelapse_headend_ed25519.pub
            # Auto-generer nøglen hvis den ikke findes — nødvendig for SSH adgang til device.
            _headend_key_path  = Path.home() / ".ssh" / "timelapse_headend_ed25519"
            _headend_pubkey_path = _headend_key_path.with_suffix(".pub")
            if not _headend_pubkey_path.exists():
                progress(f"   🔑 Headend SSH keypair mangler — genererer...")
                try:
                    _headend_key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    import subprocess as _ssh_sp
                    _ssh_sp.run(
                        [
                            "ssh-keygen", "-t", "ed25519",
                            "-f", str(_headend_key_path),
                            "-N", "",
                            "-C", "timelapse-headend",
                        ],
                        check=True, capture_output=True,
                    )
                    _headend_key_path.chmod(0o600)
                    progress(f"   ✅ Headend SSH keypair genereret: {_headend_key_path}")
                except Exception as _keygen_err:
                    raise RuntimeError(
                        f"Kunne ikke generere headend SSH keypair: {_keygen_err}\n"
                        f"Kør manuelt: ssh-keygen -t ed25519 -f ~/.ssh/timelapse_headend_ed25519 -N '' -C timelapse-headend"
                    ) from _keygen_err
            _headend_ssh_pubkey = _headend_pubkey_path.read_text().strip()
            progress(f"   🔑 Headend pubkey hentet: {_headend_pubkey_path.name}")
            _tunnel_host, _tunnel_port, _tunnel_user = _edge_provisioning.resolve_tunnel_settings(headend_url)

            inject_result = inject_edge_image(
                target=target,
                rootfs_tar=result["output_path"],
                headend_url=headend_url,
                bootstrap_token=bootstrap_token,
                gpg_key_id=gpg_key_id,
                progress_cb=progress,
                repo_root=str(_repo_root()),
                output_dir=output_dir,
                wifi_ssid=wifi_ssid,
                wifi_password=wifi_password,
                wifi_country=wifi_country,
                headend_ssh_pubkey=_headend_ssh_pubkey,
                device_ssh_privkey="",
                ssh_tunnel_port=_ssh_tunnel_port,
                tunnel_headend_host=_tunnel_host,
                tunnel_headend_port=_tunnel_port,
                tunnel_headend_user=_tunnel_user,
                interactive_shell_enabled=interactive_shell_enabled,
                bt_totp_secret=_bt_totp_secret,
                bt_totp_sid=_bt_totp_sid,
                local_mgmt_hostname=_local_tls["hostname"],
                local_mgmt_cert_pem=_local_tls["certificate_pem"],
                local_mgmt_key_pem=_local_tls["private_key_pem"],
                edge_local_ca_pem=_local_tls["ca_certificate_pem"],
                expected_device_id=_resolved_device_id,
            )
            # Merge injection-resultater ind i result
            result.update({
                "filename":          inject_result["filename"],
                "output_path":       inject_result["output_path"],
                "sha256":            inject_result["sha256"],
                "size_bytes":        inject_result["size_bytes"],
                "token_baked_in":    inject_result["token_baked_in"],
                "flash_instructions": inject_result["flash_instructions"],
                "mode":              "flashable",
                "artifact_type":     "flashable_disk_image",
            })
        else:
            result["mode"] = "rootfs"
            result["artifact_type"] = "edge_disk_image"

        # ── Registrér artifact i database ─────────────────────────────────
        db = db_factory()
        try:
            created_at = now_utc()
            with open(result["manifest_path"], encoding="utf-8") as f:
                manifest_json = f.read()
            artifact = UpdateArtifact(
                artifact_id=result["artifact_id"],
                artifact_type=result.get("artifact_type", "edge_disk_image"),
                version=result.get("created_at", created_at.isoformat()),
                source_commit=_git_text(["rev-parse", "HEAD"]) or "unknown",
                source_ref=_git_text(["rev-parse", "--abbrev-ref", "HEAD"]) or "main",
                filename=result["filename"],
                storage_path=result["output_path"],
                size_bytes=result["size_bytes"],
                sha256=result["sha256"],
                manifest_json=manifest_json,
                sbom_ref=f"sbom:os={result.get('sbom_os_count',0)},venv={result.get('sbom_venv_count',0)}",
                signature=result["signature"],
                signed_by=result["signed_by"],
                signed_at=created_at,
                created_at=created_at,
            )
            db.add(artifact)
            db.commit()
            result["db_artifact_id"] = artifact.id
            progress(f"✅ Artifact registreret i database: {result['artifact_id']}")
        finally:
            db.close()

        _edge_disk_build_status["result"] = result
        _edge_disk_build_status["running"] = False
    except Exception as exc:
        _edge_disk_build_status["error"] = str(exc)
        _edge_disk_build_status["running"] = False
        _edge_disk_build_status["progress"].append(f"❌ Build fejlede: {exc}")
        log.error("Edge disk image build fejlede: %s", exc, exc_info=True)
    finally:
        _edge_disk_build_lock.release()


@router.post("/api/admin/edge-provisioning/build-disk-image")
def trigger_edge_disk_image_build(
    body: DiskImageBuildRequest = DiskImageBuildRequest(),
    current_user=require_role("super_admin", "admin"),
    db: Session = Depends(get_db),
):
    """
    Start baggrunds-build af edge image.

    mode="rootfs"    → Docker buildx arm64/armhf → rootfs.tar.gz (hurtig, ~5 min)
    mode="flashable" → rootfs + injection → flashbart .img.gz klar til SSD (langsom, ~20 min)

    Angiv target for hardware-specifik build:
      orangepi4pro, orangepi-pc-plus, rpi4, rpi5
      (jetson-orin-nano understøttes ikke — brug install_timelapse_edge.sh)

    Poll GET /api/admin/edge-provisioning/disk-image-status for fremgang.
    """
    from main import _repo_root, _headend_api_url
    # Validér target
    hw_dir = _repo_root() / "headend" / "tools" / "hardware"
    available_targets = sorted(p.parent.name for p in hw_dir.glob("*/target.yaml"))
    if body.target not in available_targets:
        raise HTTPException(status_code=400, detail=f"Ukendt target '{body.target}'. Tilgængelige: {available_targets}")
    if body.mode == "flashable" and not body.camera_id:
        raise HTTPException(
            status_code=400,
            detail="Flashbart image kræver en valgt kameralokation, så en unik lokal adgang kan provisioneres",
        )
    if body.mode == "flashable" and not body.expected_device_id:
        active_assignment = db.query(DeviceAssignment).filter(
            DeviceAssignment.camera_id == body.camera_id,
            DeviceAssignment.unassigned_at.is_(None),
        ).first() if body.camera_id else None
        if not active_assignment:
            raise HTTPException(
                status_code=400,
                detail="Angiv fysisk Edge-ID fra mærkat eller QR-kode, før et flashbart image kan bygges.",
            )

    if not _edge_disk_build_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Et edge disk image build kører allerede")

    global _edge_disk_build_status
    _edge_disk_build_status = {
        "running": True, "progress": [], "error": None, "result": None,
        "target": body.target, "mode": body.mode,
    }

    headend_url = _headend_api_url(db, os.getenv("TIMELAPSE_HEADEND_URL"))
    gpg_key_id = os.getenv("CHANGE_TICKET_GPG_KEY") or os.getenv("TIMELAPSE_GPG_KEY")
    output_dir = str(_edge_image_storage_dir())
    os.makedirs(output_dir, exist_ok=True)

    from database import SessionLocal as _SessionLocal
    t = _threading.Thread(
        target=_run_edge_disk_image_build,
        args=(headend_url, gpg_key_id, output_dir, _SessionLocal),
        kwargs={
            "target": body.target,
            "mode": body.mode,
            "bootstrap_token": body.bootstrap_token,
            "wifi_ssid": body.wifi_ssid,
            "wifi_password": body.wifi_password,
            "wifi_country": body.wifi_country or "DK",
            "camera_id": body.camera_id,
            "expected_device_id": body.expected_device_id.strip(),
            "interactive_shell_enabled": body.interactive_shell_enabled,
        },
        daemon=True,
        name="edge-disk-image-build",
    )
    t.start()
    return {
        "status": "started",
        "target": body.target,
        "mode": body.mode,
        "message": f"Build startet [{body.target}, mode={body.mode}] — poll /api/admin/edge-provisioning/disk-image-status",
    }


@router.get("/api/admin/edge-provisioning/disk-image-status")
def edge_disk_image_status(_user=require_role("super_admin", "admin")):
    """Poll build-fremgang for edge disk image."""
    s = _edge_disk_build_status
    return {
        "running":  s["running"],
        "progress": s["progress"],
        "error":    s["error"],
        "result":   s["result"],
        "ready":    not s["running"] and s["result"] is not None,
        "target":   s.get("target"),
        "mode":     s.get("mode"),
    }


@router.get("/api/admin/edge-provisioning/targets")
def list_edge_targets(_user=require_role("super_admin", "admin")):
    """List tilgængelige hardware targets til edge image build."""
    from main import _repo_root
    hw_dir = _repo_root() / "headend" / "tools" / "hardware"
    return {"targets": _edge_provisioning.load_hardware_targets(hw_dir, log)}


@router.get("/api/admin/edge-provisioning/disk-images")
def list_flashable_disk_images(_user=require_role("super_admin", "admin"), db: Session = Depends(get_db)):
    """List alle flashable disk images (klar til WiFi-injektion eller download)."""
    artifacts = (
        db.query(UpdateArtifact)
        .filter(UpdateArtifact.artifact_type.in_(["edge_disk_image", "flashable_disk_image"]))
        .order_by(UpdateArtifact.created_at.desc())
        .limit(50)
        .all()
    )
    entries = [
        {
            "artifact_id": a.artifact_id,
            "filename": a.filename,
            "artifact_type": a.artifact_type,
            "size_bytes": a.size_bytes,
            "sha256": a.sha256,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "exists_on_disk": bool(a.storage_path and os.path.exists(a.storage_path)),
            "source": "database",
        }
        for a in artifacts
    ]
    seen = {e["artifact_id"] for e in entries} | {e["filename"] for e in entries if e.get("filename")}
    for entry in _edge_image_file_entries(_edge_image_storage_dir()):
        if entry["artifact_id"] not in seen and entry["filename"] not in seen:
            entries.append({k: v for k, v in entry.items() if k != "storage_path"})
            seen.add(entry["artifact_id"])
            seen.add(entry["filename"])
    return sorted(entries, key=lambda e: e.get("created_at") or "", reverse=True)[:100]


@router.get("/api/admin/edge-provisioning/disk-image-download/{artifact_id}")
def download_edge_disk_image(artifact_id: str, _user=require_role("super_admin", "admin"), db: Session = Depends(get_db)):
    """Download færdigt edge disk image (rootfs tarball)."""
    from fastapi.responses import FileResponse
    image_path, filename = _resolve_edge_image_path(artifact_id, db)
    return FileResponse(
        str(image_path),
        media_type="application/octet-stream",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


class DeleteDiskImageRequest(BaseModel):
    confirm_artifact_id: str
    reason: str


@router.delete("/api/admin/edge-provisioning/disk-images/{artifact_id}")
def delete_edge_disk_image(
    artifact_id: str,
    body: DeleteDiskImageRequest,
    current_user=require_role("super_admin"),
    db: Session = Depends(get_db),
):
    """Delete only the derived image payload; retain manifest and audit evidence."""
    if body.confirm_artifact_id != artifact_id:
        raise HTTPException(status_code=422, detail="Artifact-ID bekræftelse matcher ikke")
    reason = body.reason.strip()
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="Begrundelse er påkrævet")
    image_path, filename = _resolve_edge_image_path(artifact_id, db)
    storage_dir = _edge_image_storage_dir(create=False).resolve()
    resolved = image_path.resolve()
    if storage_dir not in resolved.parents:
        raise HTTPException(status_code=409, detail="Image ligger uden for den konfigurerede artifact-mappe")
    if not (filename.endswith(".img.gz") or filename.endswith(".rootfs.tar.gz")):
        raise HTTPException(status_code=409, detail="Kun afledte Edge image-filer kan slettes")
    size_bytes = resolved.stat().st_size
    resolved.unlink()

    artifact = db.query(UpdateArtifact).filter_by(artifact_id=artifact_id).first()
    if artifact:
        artifact.storage_path = None
    db.add(Event(
        device_id="HEADEND",
        level="WARNING",
        category="edge_image_deleted",
        message=f"Edge image payload slettet: {artifact_id}",
        extra=json.dumps({
            "artifact_id": artifact_id,
            "filename": filename,
            "size_bytes": size_bytes,
            "reason": reason,
            "deleted_by": current_user.username,
            "manifest_retained": True,
        }),
    ))
    db.commit()
    return {"ok": True, "artifact_id": artifact_id, "filename": filename, "manifest_retained": True}


class InjectWifiRequest(BaseModel):
    artifact_id: str
    wifi_ssid: str
    wifi_password: str
    wifi_country: str = "DK"
    wifi_method: str = "auto"   # "auto" | "netplan" | "wpa_supplicant"
    camera_id: Optional[str] = None  # bruges til at hente SSH-nøgler fra DB


_wifi_inject_status: dict = {
    "running": False, "progress": [], "error": None, "result": None,
}
_wifi_inject_lock = _threading.Lock()


def _run_wifi_inject(
    artifact_id: str,
    wifi_ssid: str,
    wifi_password: str,
    wifi_country: str,
    wifi_method: str,
    db_factory,
    camera_id: str | None = None,
) -> None:
    """Background thread: injectér WiFi i eksisterende flashbart image."""
    from main import _repo_root, _headend_api_url
    global _wifi_inject_status

    def progress(msg: str) -> None:
        _wifi_inject_status["progress"].append(msg)
        log.info("[wifi-inject] %s", msg)

    try:
        try:
            from headend.tools.inject_wifi_image import inject_wifi_image
        except ImportError:
            import sys
            sys.path.insert(0, str(_repo_root() / "headend"))
            from tools.inject_wifi_image import inject_wifi_image  # type: ignore

        source = _edge_provisioning.require_signed_source_artifact(artifact_id, db_factory)
        fname = source["filename"]
        gz_path = source["storage_path"]
        output_dir = source["output_dir"]

        target_id: str | None = None
        for known in ["orangepi4pro", "orangepi-pc-plus", "rpi4", "rpi5", "jetson-orin-nano"]:
            if known in fname:
                target_id = known
                break

        # Hent kun ikke-private SSH metadata fra Camera hvis camera_id er angivet.
        headend_ssh_public_key: str | None = None
        reverse_tunnel_port: int | None = None
        if camera_id:
            db_ssh = db_factory()
            try:
                from database import Camera as _Camera
                cam_ssh = db_ssh.query(_Camera).filter_by(id=camera_id).first()
                if cam_ssh:
                    reverse_tunnel_port = getattr(cam_ssh, "reverse_tunnel_port", None)
            finally:
                db_ssh.close()
            # Hent headend public key
            try:
                import os as _os
                _pub = _os.path.expanduser("~/.ssh/timelapse_headend_ed25519.pub")
                if _os.path.exists(_pub):
                    headend_ssh_public_key = open(_pub).read().strip()
            except Exception:
                pass

        db_url = db_factory()
        try:
            edge_url = _headend_api_url(db_url, os.getenv("TIMELAPSE_HEADEND_URL"))
        finally:
            db_url.close()
        tunnel_host, tunnel_port, tunnel_user = _edge_provisioning.resolve_tunnel_settings(edge_url)

        # Lang operation — ingen åben DB-session
        result = inject_wifi_image(
            gz_path=gz_path,
            wifi_ssid=wifi_ssid,
            wifi_password=wifi_password,
            wifi_country=wifi_country,
            wifi_method=wifi_method,
            target_id=target_id,
            output_dir=output_dir,
            progress_cb=progress,
            repo_root=str(_repo_root()),
            ssh_private_key=None,
            headend_ssh_public_key=headend_ssh_public_key,
            reverse_tunnel_port=reverse_tunnel_port,
            headend_host=tunnel_host,
            headend_port=tunnel_port,
            headend_user=tunnel_user,
        )

        signed_manifest = _edge_provisioning.create_signed_wifi_manifest(
            artifact_id=artifact_id,
            source_artifact_id=source["artifact_id"],
            source_sha256=source["sha256"],
            result=result,
            output_dir=output_dir,
            wifi_country=wifi_country,
            ssh_configured=False,
            progress=progress,
        )
        new_artifact_id = signed_manifest["artifact_id"]
        created_at = signed_manifest["created_at"]

        # Ny DB-session til INSERT (den gamle er timed out)
        db_write = db_factory()
        try:
            new_artifact = UpdateArtifact(
                artifact_id=new_artifact_id,
                artifact_type="flashable_disk_image",
                filename=result["filename"],
                storage_path=result["output_path"],
                size_bytes=result["size_bytes"],
                sha256=result["sha256"],
                signature=signed_manifest["signature"],
                signed_by=signed_manifest["signed_by"],
                signed_at=created_at,
                created_at=created_at,
                manifest_json=signed_manifest["manifest_json"],
            )
            db_write.add(new_artifact)
            db_write.commit()
            _wifi_inject_status.update({
                "running": False,
                "result": {
                    "artifact_id": new_artifact_id,
                    "filename": result["filename"],
                    "sha256": result["sha256"],
                    "size_bytes": result["size_bytes"],
                    "wifi_ssid": wifi_ssid,
                },
                "error": None,
            })
            progress(f"✅ WiFi-injiceret artifact registreret: {new_artifact_id}")
        finally:
            db_write.close()

    except Exception as exc:
        log.exception("[wifi-inject] Fejl")
        _wifi_inject_status["running"] = False
        _wifi_inject_status["error"] = str(exc)


@router.post("/api/admin/edge-provisioning/inject-wifi")
def inject_wifi_endpoint(
    body: InjectWifiRequest,
    _user=require_role("super_admin", "admin"),
):
    """Injectér WiFi-konfiguration i et eksisterende flashbart image."""
    with _wifi_inject_lock:
        if _wifi_inject_status.get("running"):
            raise HTTPException(status_code=409, detail="En WiFi-injektion kører allerede")

        _wifi_inject_status.update({
            "running": True, "progress": ["Starter WiFi-injektion..."],
            "error": None, "result": None,
            "artifact_id": body.artifact_id, "wifi_ssid": body.wifi_ssid,
        })

    from database import SessionLocal as _SessionLocal
    t = _threading.Thread(
        target=_run_wifi_inject,
        args=(body.artifact_id, body.wifi_ssid, body.wifi_password,
              body.wifi_country, body.wifi_method, _SessionLocal,
              body.camera_id),
        daemon=True,
        name="wifi-inject",
    )
    t.start()
    return {
        "status": "started",
        "artifact_id": body.artifact_id,
        "message": "WiFi-injektion startet — poll /api/admin/edge-provisioning/wifi-inject-status",
    }


@router.get("/api/admin/edge-provisioning/wifi-inject-status")
def wifi_inject_status(_user=require_role("super_admin", "admin")):
    """Hent status for igangværende WiFi-injektion."""
    return _wifi_inject_status


