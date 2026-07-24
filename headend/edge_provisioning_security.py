"""Security helpers shared by Edge image provisioning workflows."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def load_hardware_targets(hardware_dir: Path, logger) -> list[dict]:
    """Load target profiles and expose flash trust without optimistic fallbacks."""
    import yaml

    targets: list[dict] = []
    for target_yaml in sorted(hardware_dir.glob("*/target.yaml")):
        try:
            target = yaml.safe_load(target_yaml.read_text(encoding="utf-8")) or {}
            base = target.get("base_image", {})
            is_script = base.get("type") == "install_script"
            base_sha = str(base.get("sha256") or "")
            base_pinned = bool(re.fullmatch(r"[0-9a-fA-F]{64}", base_sha))
            targets.append(
                {
                    "id": target.get("id", target_yaml.parent.name),
                    "display_name": target.get("display_name", target_yaml.parent.name),
                    "arch": target.get("arch", "arm64"),
                    "soc": target.get("soc"),
                    "hal_class": target.get("hal_class"),
                    "flashable": not is_script and base_pinned,
                    "install_script": is_script,
                    "base_image_pinned": base_pinned,
                    "blocked_reason": (
                        None
                        if is_script or base_pinned
                        else "Base-image mangler en valideret SHA-256 i target.yaml"
                    ),
                }
            )
        except Exception as exc:
            logger.warning("Kunne ikke læse %s: %s", target_yaml, exc)
    return targets


def resolve_tunnel_settings(headend_url: str) -> tuple[str, int, str]:
    """Resolve the dedicated reverse-tunnel ingress from governed settings."""
    host = os.getenv("TIMELAPSE_TUNNEL_HOST") or urlparse(headend_url).hostname or ""
    port = int(os.getenv("TIMELAPSE_TUNNEL_PORT", "22222"))
    user = os.getenv("TIMELAPSE_TUNNEL_USER", "tunnel")
    return host, port, user


def require_signed_source_artifact(artifact_id: str, db_factory) -> dict:
    """Resolve a signed image artifact and reject direct filesystem paths."""
    from database import UpdateArtifact

    if artifact_id.startswith(("/", "~")):
        raise ValueError(
            "Direkte filstier er ikke tilladt i UI-flowet. Registrér og signér "
            "kilde-imaget i artifact-kataloget først."
        )

    db = db_factory()
    try:
        artifact = (
            db.query(UpdateArtifact)
            .filter(
                UpdateArtifact.artifact_id == artifact_id,
                UpdateArtifact.artifact_type.in_(["edge_disk_image", "flashable_disk_image"]),
            )
            .first()
        )
        if not artifact:
            raise ValueError(f"Artifact ikke fundet: {artifact_id}")
        if not artifact.storage_path or not os.path.exists(artifact.storage_path):
            raise FileNotFoundError(f"Image-fil ikke tilgængelig: {artifact.storage_path}")
        if not artifact.signature or not artifact.signed_by or not artifact.manifest_json:
            raise ValueError(f"Kilde-artifact {artifact_id} mangler signatur eller manifest")
        return {
            "artifact_id": artifact.artifact_id,
            "filename": artifact.filename or "",
            "storage_path": artifact.storage_path,
            "output_dir": os.path.dirname(artifact.storage_path),
            "sha256": artifact.sha256 or "",
        }
    finally:
        db.close()


def create_signed_wifi_manifest(
    *,
    artifact_id: str,
    source_artifact_id: str,
    source_sha256: str,
    result: dict,
    output_dir: str,
    wifi_country: str,
    ssh_configured: bool,
    progress,
) -> dict:
    """Create and persist the provenance manifest for a reconfigured image."""
    try:
        from headend.tools.inject_edge_image import _sign_manifest
    except ImportError:
        from tools.inject_edge_image import _sign_manifest

    created_at = datetime.now(timezone.utc)
    new_artifact_id = (
        f"TL-FLASH-WIFI-{artifact_id[-8:]}-{created_at.strftime('%Y%m%d%H%M%S')}"
    )
    manifest = {
        "schema": "timelapse.flashable_image.reconfiguration.v1",
        "artifact_id": new_artifact_id,
        "artifact_type": "flashable_disk_image",
        "source_artifact_id": source_artifact_id,
        "source_sha256": source_sha256,
        "image": {
            "filename": result["filename"],
            "sha256": result["sha256"],
            "size_bytes": result["size_bytes"],
        },
        "configuration": {
            "wifi_configured": True,
            "wifi_country": wifi_country,
            "wifi_method": result["wifi_method"],
            "reverse_tunnel_configured": ssh_configured,
        },
        "created_at": created_at.isoformat(),
    }
    unsigned = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
    key_id = os.getenv("CHANGE_TICKET_GPG_KEY") or os.getenv("TIMELAPSE_GPG_KEY")
    signature, signed_by = _sign_manifest(unsigned, key_id, progress)
    manifest.update(signature=signature, signed_by=signed_by)
    manifest_json = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
    Path(output_dir, f"{new_artifact_id}.manifest.json").write_text(
        manifest_json, encoding="utf-8"
    )
    return {
        "artifact_id": new_artifact_id,
        "created_at": created_at,
        "signature": signature,
        "signed_by": signed_by,
        "manifest_json": manifest_json,
    }
