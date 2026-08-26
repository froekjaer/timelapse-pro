"""Headend Generator API — klargør en NY headend (staging/prod) fra UI'et.

Analog til "Klargør ny Edge": genererer miljø-konfigurationsfil, one-time
bootstrap-token (node_type=headend ved enrollment) og en downloadbar
installationspakke (.tar.gz) med bootstrap-scripts + trin-for-trin README.

Trust-model (HEADEND_GENERATOR_v1.md): pakken indeholder KUN konfiguration,
token og de to bootstrap-/orkestrator-scripts. Selve installationen (apply/
enroll) køres fra den GPG-verificerede GitHub-release, som bootstrap-scriptet
henter og verificerer på målmaskinen — aldrig fra denne pakke.

Se også: INSTALLATIONSMANUAL_HEADEND_GENERATOR_v1.md,
Claude_REVIEW_Generatorer_Edge_Headend_2026-07-17.md (GEN-01/02: SFTP-trinnet
er fortsat manuelt og fremhæves i README'en).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets as _secrets
import shlex
import subprocess
import tarfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import BootstrapToken, get_db
from auth import get_current_user

router = APIRouter(prefix="/api/headend/generator", tags=["Headend Generator"])

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORBIDDEN_PORTS = {21, 22, 80, 443}  # CrushFTP/system — må ALDRIG bruges (PORTS.md)
_ENVIRONMENTS = {"staging", "prod"}
_ADMIN_ROLES = {"admin", "super_admin"}
_BUNDLE_SCRIPTS = ("bootstrap_headend_macos.sh", "headend_generator.sh")
_BUNDLE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.tar\.gz$")
_FULL_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DEVICE_ID_RE = re.compile(r"^TL-[A-Za-z0-9][A-Za-z0-9._-]{2,95}$")
_ACCOUNT_RE = re.compile(r"^_?[a-z][a-z0-9_-]{0,30}$")
_DB_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _safe_bundle_name(name: str) -> str:
    """Afvis alt der ikke er et rent bundlefilnavn (ingen stier/traversal)."""
    candidate = str(name or "").strip()
    if "/" in candidate or "\\" in candidate or ".." in candidate or not _BUNDLE_NAME_RE.match(candidate):
        raise ValueError("Ugyldigt bundle-filnavn")
    return candidate


def _setting(key: str, default: str = "") -> str:
    """DB-setting (Settings-tabellen, UI-redigerbar) — husreglen: variable i DB, ikke i kode."""
    from database import SessionLocal
    from main import _get_setting
    db = SessionLocal()
    try:
        return _get_setting(db, key, default)
    finally:
        db.close()


def _bundle_storage_dir(*, create: bool = True) -> Path:
    """`headend-images` — søskendekatalog til edge-images (samme opløsningsprincip).

    1. `TIMELAPSE_HEADEND_IMAGE_DIR` (env) hvis sat.
    2. DB-settingen `headend_image_artifact_dir` (UI-redigerbar, spejler
       edge-pendantens `edge_image_artifact_dir`).
    3. Ellers: forælderen til den aktive edge-image-mappe + `headend-images`,
       så pakkerne altid ligger VED SIDEN AF edge-images uanset hvor de bor
       (R&D-stier, lagerregisterets `edge-artifacts`-rolle eller repo-fallback).
    """
    configured = os.getenv("TIMELAPSE_HEADEND_IMAGE_DIR") or _setting("headend_image_artifact_dir", "")
    if configured:
        candidate = Path(configured).expanduser()
    else:
        from main import _edge_image_storage_dir
        candidate = _edge_image_storage_dir(create=create).parent / "headend-images"
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
        probe = candidate / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    return candidate


def _current_viewer(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Ikke autentificeret")
    return user


def _require_platform_admin(user=Depends(_current_viewer)):
    if user.role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Headend-generator kræver administrator")
    return user


def _signed_release_catalog() -> list[dict]:
    """Return annotated tags whose signature is trusted by this Headend.

    The generator deliberately uses the already controlled local checkout.
    Fetching or trusting new release material remains part of the update and
    promotion flow; opening this UI never performs a network operation.
    """
    refs = subprocess.run(
        [
            "git",
            "-C",
            str(_REPO_ROOT),
            "for-each-ref",
            "--sort=-creatordate",
            "--format=%(refname:short)%09%(objecttype)%09%(*objectname)%09%(creatordate:iso8601-strict)%09%(subject)",
            "refs/tags",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if refs.returncode != 0:
        raise RuntimeError((refs.stderr or "Kunne ikke læse lokale release-tags").strip())

    releases: list[dict] = []
    for line in refs.stdout.splitlines():
        fields = line.split("\t", 4)
        if len(fields) != 5:
            continue
        tag, object_type, commit, created_at, subject = fields
        # Lightweight/archive tags are not release artifacts.
        if object_type != "tag" or not _FULL_COMMIT_RE.fullmatch(commit.lower()):
            continue
        verification = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "verify-tag", tag],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if verification.returncode != 0:
            continue
        releases.append(
            {
                "tag": tag,
                "commit": commit.lower(),
                "created_at": created_at,
                "subject": subject,
                "signature_status": "trusted",
            }
        )
    return releases


def _validate_release_selection(spec: dict, releases: list[dict] | None = None) -> dict:
    """Bind a requested tag to its single trusted full commit SHA."""
    tag = spec["release_tag"]
    commit = spec["expected_commit"].lower()
    if not tag:
        raise ValueError("Vælg et signeret release-tag")
    if not _FULL_COMMIT_RE.fullmatch(commit):
        raise ValueError("Vælg den fulde 40-tegns commit-SHA for releasen")

    catalog = releases if releases is not None else _signed_release_catalog()
    selected = next((release for release in catalog if release["tag"] == tag), None)
    if not selected:
        raise ValueError("Release-tagget findes ikke i Headendens katalog over betroede signerede releases")
    if selected["commit"] != commit:
        raise ValueError(
            f"Commit-SHA matcher ikke {tag}; den verificerede SHA er {selected['commit']}"
        )
    spec["expected_commit"] = commit
    return spec


def _validate_request(payload: dict) -> dict:
    """Ren valideringshjælper — testbar uden DB/FastAPI."""
    environment = str(payload.get("environment") or "").strip().lower()
    if environment not in _ENVIRONMENTS:
        raise ValueError("environment skal være 'staging' eller 'prod'")
    domain = str(payload.get("domain") or "").strip().lower()
    if not domain or "/" in domain or " " in domain or "." not in domain:
        raise ValueError("domain skal være et gyldigt backend-domæne (fx staging.timelapse-pro.dk)")
    try:
        backend_port = int(payload.get("backend_port") or 8443)
    except (TypeError, ValueError):
        raise ValueError("backend_port skal være et heltal")
    if backend_port in _FORBIDDEN_PORTS:
        raise ValueError(f"Port {backend_port} er forbudt — CrushFTP ejer 21/22/80/443 (PORTS.md)")
    if not (1024 <= backend_port <= 65535):
        raise ValueError("backend_port skal være 1024-65535")
    device_id = str(payload.get("device_id") or "").strip() or f"TL-HEADEND-{environment.upper()}-1"
    if not _DEVICE_ID_RE.fullmatch(device_id):
        raise ValueError("device_id skal starte med 'TL-' og kun indeholde bogstaver, tal, punktum, _ og -")
    expires_hours = max(1, min(int(payload.get("expires_hours") or 48), 24 * 14))
    spec = {
        "environment": environment,
        "domain": domain,
        "backend_port": backend_port,
        "device_id": device_id,
        "data_dir": str(
            payload.get("data_dir") or "/Users/Shared/TimeLapsePro/data/canonical-images"
        ).strip(),
        "repo_dir": str(
            payload.get("repo_dir") or f"/Users/Shared/TimeLapsePro/releases/{environment}"
        ).strip(),
        "service_user": str(payload.get("service_user") or "_timelapse").strip(),
        "service_group": str(payload.get("service_group") or "_timelapse").strip(),
        "service_home": str(payload.get("service_home") or "/var/lib/timelapse").strip(),
        "tunnel_host": str(payload.get("tunnel_host") or domain).strip().lower(),
        "tunnel_port": int(payload.get("tunnel_port") or 22222),
        "tunnel_user": str(payload.get("tunnel_user") or "tunnel").strip(),
        "db_name": str(payload.get("db_name") or "timelapse_db").strip(),
        "db_user": str(payload.get("db_user") or "timelapse").strip(),
        "repo_url": str(payload.get("repo_url") or "").strip(),
        "release_tag": str(payload.get("release_tag") or "").strip(),
        "expected_commit": str(payload.get("expected_commit") or "").strip(),
        "expires_hours": expires_hours,
    }
    for field in ("service_user", "service_group", "tunnel_user"):
        if not _ACCOUNT_RE.fullmatch(spec[field]):
            raise ValueError(f"{field} er ikke et gyldigt lokalt macOS-kontonavn")
    for field in ("db_name", "db_user"):
        if not _DB_IDENTIFIER_RE.fullmatch(spec[field]):
            raise ValueError(f"{field} er ikke et gyldigt PostgreSQL-navn")
    for field in ("data_dir", "repo_dir", "service_home"):
        value = spec[field]
        if not value.startswith("/") or "\n" in value or "\r" in value:
            raise ValueError(f"{field} skal være en absolut sti uden linjeskift")
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", spec["tunnel_host"]):
        raise ValueError("tunnel_host skal være et gyldigt hostnavn")
    if not 1024 <= spec["tunnel_port"] <= 65535 or spec["tunnel_port"] in _FORBIDDEN_PORTS | {8080}:
        raise ValueError("tunnel_port skal være 1024-65535 og må ikke være reserveret")
    return spec


def _render_conf(spec: dict) -> str:
    def assignment(name: str, value: object) -> str:
        return f"{name}={shlex.quote(str(value))}"

    return f"""# TimeLapse Pro — miljøkonfiguration ({spec['environment']})
# Genereret af Headend Generator {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}
# CrushFTP ejer 21/22/80/443 på denne maskine — TimeLapse rører dem ALDRIG.

{assignment('TL_ENV', spec['environment'])}
{assignment('TL_DOMAIN_BACKEND', spec['domain'])}
{assignment('TL_BACKEND_PORT', spec['backend_port'])}

# Peger BEVIDST på den GPG-verificerede release (stage-fasen) — ikke en arbejdskopi.
{assignment('TL_REPO_DIR', spec['repo_dir'])}

{assignment('TL_DATA_DIR', spec['data_dir'])}
{assignment('TL_DB_NAME', spec['db_name'])}
{assignment('TL_DB_USER', spec['db_user'])}
{assignment('TL_SERVICE_USER', spec['service_user'])}
{assignment('TL_SERVICE_GROUP', spec['service_group'])}
{assignment('TL_SERVICE_HOME', spec['service_home'])}
{assignment('TL_TUNNEL_HOST', spec['tunnel_host'])}
{assignment('TL_TUNNEL_PORT', spec['tunnel_port'])}
{assignment('TL_TUNNEL_USER', spec['tunnel_user'])}
"""


def _render_commands(spec: dict) -> list[str]:
    values = {
        key: shlex.quote(str(spec[key]))
        for key in ("repo_url", "release_tag", "expected_commit", "repo_dir", "device_id")
    }
    return [
        "tar -xzf timelapse-headend-installer-*.tar.gz && cd headend-installer",
        f"./headend_generator.sh --config ./{spec['environment']}.conf "
        f"--repo-url {values['repo_url']} --release-tag {values['release_tag']} "
        f"--expected-commit {values['expected_commit']} "
        f"--destination {values['repo_dir']} --device-id {values['device_id']} "
        "--bootstrap-token-file ./bootstrap-token",
    ]


def _render_readme(spec: dict) -> str:
    commands = "\n".join(_render_commands(spec))
    return f"""# TimeLapse Pro — Installationspakke: ny headend ({spec['environment']})

Genereret: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} · Device-ID: {spec['device_id']}
Fuld manual: Dokumentation/INSTALLATIONSMANUAL_HEADEND_GENERATOR_v1.md (i releasen).

## Indhold
- `{spec['environment']}.conf` — miljøkonfiguration (peger på den verificerede release)
- `bootstrap-token` — ENGANGS-token til CMDB-enrollment (udløber {spec['expires_hours']} timer efter generering — behandl som hemmelighed)
- `bootstrap_headend_macos.sh` — Fase 0 preflight + Fase 1 signeret release-hentning
- `headend_generator.sh` — orkestrator der kæder alle fire faser med gates

## Sameksistens med CrushFTP (ufravigeligt)
CrushFTP ejer 21/22/80/443 på målmaskinen. Alt TimeLapse kører på port {spec['backend_port']}
(UI/API), 22222 (SFTP-ingress) og loopback. Preflight NÆGTER at fortsætte hvis
port {spec['backend_port']} er optaget, og installeren afviser 21/22/80/443 hårdt.
Certifikat udstedes via DNS-01 og rører ingen port.

## Kørsel (på den NYE Mac)
Forudsætninger: Homebrew-pakker + GPG-release-nøgle importeret (manual §1).

```bash
{commands}
```

Orkestratoren stopper ved hver gate og ved enhver fejl (fail-closed). Apply og
enroll køres fra den GPG-verificerede release i --destination — aldrig fra
denne pakke.

## ⚠️ Manuelle trin pakken IKKE dækker (manual §5-§7)
1. DNS-01-certifikat (certbot-dns-cloudflare) + genkør apply for fuldt SSL.
2. FØRSTE LOGIN med installerens unikke initiale adgangskode → MFA + nyt
   password FØR offentlig eksponering. `admin/changeme` er forbudt i staging/prod.
3. SFTP-ingress på 22222 (Fase 2b — GEN-01/GEN-02): dedikeret sshd-socket,
   hardening-profil, per-site RBAC-regler OG DB-settings `sftp_port=22222`.
   Uden dette trin peger edge-upload-fallback på port 22 = CrushFTP!
4. Backup: sæt eksplicit skrivbar BACKUP_BASE (R09) + restore-test.
"""


def _apply_db_defaults(spec: dict) -> dict:
    """Udfyld tomme felter fra DB-settings (UI-redigerbare) — kode-literal kun som sidste udvej."""
    if not spec["repo_url"]:
        spec["repo_url"] = _setting("headend_repo_url", "git@github.com:froekjaer/timelapse-pro.git")
    return spec


@router.get("/releases")
def list_trusted_releases(_user=Depends(_require_platform_admin)):
    """Valid release/commit pairs for the generator dropdowns."""
    try:
        releases = _signed_release_catalog()
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=f"Release-kataloget kunne ikke læses: {exc}")
    return {
        "source": "local_trusted_git_tags",
        "repo": str(_REPO_ROOT),
        "releases": releases,
    }


@router.post("/prepare")
def prepare_headend(payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    """Validér ønsket miljø, udsted one-time bootstrap-token og returnér conf + kommandoer."""
    try:
        spec = _validate_release_selection(_apply_db_defaults(_validate_request(payload or {})))
    except (ValueError, OSError, subprocess.SubprocessError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Revokér tidligere åbne tokens for samme headend-identitet (samme princip som edge-prepare).
    now = datetime.now(timezone.utc)
    for open_token in (
        db.query(BootstrapToken)
        .filter_by(device_label=spec["device_id"], used_at=None, revoked=False)
        .all()
    ):
        open_token.revoked = True

    token_value = f"tlp-{_secrets.token_urlsafe(32)}"
    record = BootstrapToken(
        token=token_value,
        device_label=spec["device_id"],
        created_by=user.username,
        expires_at=now + timedelta(hours=spec["expires_hours"]),
    )
    db.add(record)
    db.commit()

    return {
        "status": "prepared",
        "device_id": spec["device_id"],
        "environment": spec["environment"],
        "backend_url": f"https://{spec['domain']}:{spec['backend_port']}",
        "token": token_value,
        "expires_at": record.expires_at.isoformat(),
        "conf": _render_conf(spec),
        "commands": _render_commands(spec),
        "manual": "Dokumentation/INSTALLATIONSMANUAL_HEADEND_GENERATOR_v1.md",
        "warnings": [
            "Fase 2b (SFTP 22222) er et manuelt trin — se README/manual §7 (GEN-01/GEN-02).",
            "Gennemfør første login FØR offentlig eksponering (GEN-07).",
        ],
    }


@router.post("/bundle")
def download_bundle(payload: dict, user=Depends(_require_platform_admin), db: Session = Depends(get_db)):
    """Byg installationspakken (.tar.gz), persistér i headend-images og returnér download."""
    try:
        spec = _validate_release_selection(_apply_db_defaults(_validate_request(payload or {})))
    except (ValueError, OSError, subprocess.SubprocessError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    token_value = str(payload.get("token") or "").strip()
    if token_value:
        record = db.query(BootstrapToken).filter_by(token=token_value, revoked=False).first()
        if not record or record.used_at is not None:
            raise HTTPException(status_code=422, detail="Tokenet er ukendt, brugt eller revokeret — kør 'Klargør' igen")
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="Tokenet er udløbet — kør 'Klargør' igen")
        if record.device_label != spec["device_id"]:
            raise HTTPException(status_code=422, detail="Tokenet tilhører en anden Headend-identitet")
    else:
        raise HTTPException(status_code=422, detail="token mangler — kør 'Klargør ny headend' først")

    buffer = io.BytesIO()
    mtime = int(time.time())

    def _add(tar: tarfile.TarFile, name: str, content: bytes, mode: int) -> None:
        info = tarfile.TarInfo(name=f"headend-installer/{name}")
        info.size = len(content)
        info.mode = mode
        info.mtime = mtime
        tar.addfile(info, io.BytesIO(content))

    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        _add(tar, "README_INSTALL.md", _render_readme(spec).encode(), 0o644)
        _add(tar, f"{spec['environment']}.conf", _render_conf(spec).encode(), 0o644)
        _add(tar, "bootstrap-token", (token_value + "\n").encode(), 0o600)
        for script_name in _BUNDLE_SCRIPTS:
            script_path = _REPO_ROOT / "deploy" / "install" / script_name
            if not script_path.is_file():
                raise HTTPException(status_code=500, detail=f"Scriptet mangler i repoet: {script_name}")
            _add(tar, script_name, script_path.read_bytes(), 0o755)

    now_ts = datetime.now(timezone.utc)
    device_slug = re.sub(r"[^A-Za-z0-9-]", "-", spec["device_id"]).strip("-").lower()
    filename = f"timelapse-headend-installer-{spec['environment']}-{device_slug}-{now_ts:%Y%m%d-%H%M%S}.tar.gz"
    content = buffer.getvalue()
    sha256 = hashlib.sha256(content).hexdigest()

    # Persistér i headend-images (søskende til edge-images) + manifest UDEN token.
    # Pakken indeholder et engangs-enrollment-token → behandl kataloget som
    # hemmeligt lager og ryd op efter brug (samme regel som flashable edge-images, GEN-09).
    storage_dir = _bundle_storage_dir()
    bundle_path = storage_dir / filename
    bundle_path.write_bytes(content)
    bundle_path.chmod(0o600)
    manifest = {
        "schema": "dk.froekjaer.timelapse.headend-installer-bundle.v1",
        "generated_at": now_ts.isoformat(),
        "environment": spec["environment"],
        "device_id": spec["device_id"],
        "domain": spec["domain"],
        "backend_port": spec["backend_port"],
        "release_tag": spec["release_tag"] or None,
        "expected_commit": spec["expected_commit"] or None,
        "sha256": sha256,
        "size_bytes": len(content),
        "created_by": user.username,
        "contains_secret": True,
        "note": "Indeholder engangs-bootstrap-token — behandl som hemmelighed, slet efter brug.",
    }
    manifest_path = storage_dir / (filename + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return Response(
        content=content,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Bundle-Sha256": sha256,
        },
    )


@router.get("/bundles")
def list_bundles(_user=Depends(_require_platform_admin)):
    """Gemte installationspakker i headend-images (nyeste først)."""
    try:
        storage_dir = _bundle_storage_dir(create=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Kan ikke bestemme headend-images-katalog: {exc}")
    bundles = []
    if storage_dir.is_dir():
        for path in sorted(storage_dir.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True):
            meta = {}
            manifest_path = path.with_name(path.name + ".manifest.json")
            if manifest_path.is_file():
                try:
                    meta = json.loads(manifest_path.read_text(encoding="utf-8"))
                except Exception:
                    meta = {"note": "manifest ulæseligt"}
            bundles.append({
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
                "environment": meta.get("environment"),
                "device_id": meta.get("device_id"),
                "sha256": meta.get("sha256"),
                "created_by": meta.get("created_by"),
            })
    return {"storage_dir": str(storage_dir), "bundles": bundles}


@router.get("/bundles/{filename}")
def download_stored_bundle(filename: str, _user=Depends(_require_platform_admin)):
    """Hent en tidligere genereret pakke fra headend-images."""
    try:
        safe_name = _safe_bundle_name(filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    path = _bundle_storage_dir(create=False) / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Pakken findes ikke (måske ryddet op efter brug)")
    return Response(
        content=path.read_bytes(),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.delete("/bundles/{filename}")
def delete_stored_bundle(filename: str, _user=Depends(_require_platform_admin)):
    """Ryd op efter brug (pakken indeholder et engangs-token). Reversibelt: flyttes til .quarantine."""
    try:
        safe_name = _safe_bundle_name(filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    storage_dir = _bundle_storage_dir(create=False)
    path = storage_dir / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Pakken findes ikke")
    quarantine = storage_dir / ".quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    path.rename(quarantine / f"{stamp}-{safe_name}")
    manifest_path = storage_dir / (safe_name + ".manifest.json")
    if manifest_path.is_file():
        manifest_path.rename(quarantine / f"{stamp}-{safe_name}.manifest.json")
    return {"status": "quarantined", "filename": safe_name}
