"""
TimeLapse Pro Edge security helpers.

Provides transitional mutual-auth request signing and artifact trust checks.
Edge still authenticates with its Bearer token, but signed requests allow
Headend to validate signal integrity and replay metadata while the fleet moves
towards per-device signing keys or mTLS.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import base64
import time
import uuid
from pathlib import Path
from typing import Any


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def request_signature_headers(
    token: str | None,
    method: str,
    path: str,
    payload: dict | None = None,
    payload_hash: str | None = None,
) -> dict[str, str]:
    if not token:
        return {}
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    body = payload_hash or (canonical_json(payload or {}) if payload else "")
    signed = "\n".join([method.upper(), path, timestamp, nonce, body])
    signature = hmac.new(token.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()
    headers = {
        "X-TLP-Signature-Alg": "hmac-sha256-v1",
        "X-TLP-Timestamp": timestamp,
        "X-TLP-Nonce": nonce,
        "X-TLP-Signature": signature,
    }
    if payload_hash:
        headers["X-TLP-Signature-Scope"] = "payload-sha256"
        headers["X-TLP-Signature-Payload-SHA256"] = payload_hash
    return headers


def edge_attestation_headers(
    base_dir: str | Path,
    device_id: str,
    method: str,
    path: str,
    payload: dict | None = None,
    payload_hash: str | None = None,
) -> dict[str, str]:
    """Sign an Edge signal with the Edge-local Ed25519 key."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key_info = ensure_edge_signing_key(base_dir, device_id)
    private_key = load_pem_private_key(Path(key_info["private_key_path"]).read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        return {}
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    body = payload_hash or (canonical_json(payload or {}) if payload else "")
    signed = "\n".join([method.upper(), path, timestamp, nonce, body])
    signature = private_key.sign(signed.encode("utf-8"))
    headers = {
        "X-TLP-Edge-Signature-Alg": "ed25519-v1",
        "X-TLP-Edge-Signature-Key": key_info["fingerprint"],
        "X-TLP-Edge-Signature-Timestamp": timestamp,
        "X-TLP-Edge-Signature-Nonce": nonce,
        "X-TLP-Edge-Signature": base64.b64encode(signature).decode("ascii"),
    }
    if payload_hash:
        headers["X-TLP-Edge-Signature-Scope"] = "payload-sha256"
        headers["X-TLP-Edge-Signature-Payload-SHA256"] = payload_hash
    return headers


def artifact_manifest_sha(manifest: dict | str | None) -> str | None:
    if manifest is None:
        return None
    if isinstance(manifest, str):
        raw = manifest
    else:
        raw = canonical_json(manifest)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def trusted_signer_fingerprints(security_cfg: dict) -> set[str]:
    signers = security_cfg.get("trusted_release_signers") or []
    return {
        str(s.get("fingerprint"))
        for s in signers
        if isinstance(s, dict) and s.get("fingerprint")
    }


def _fingerprint_material(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_update_artifact(update: dict, security_cfg: dict) -> tuple[bool, str]:
    """Validate that an update carries a trusted signed artifact manifest.

    This is a local acceptance gate before an Edge installs code. It does not
    yet perform OpenPGP verification on the Edge because the current update
    payload only carries DB material. It does enforce the invariant that app
    code must be bound to a manifest hash and a trusted Headend/release signer.
    """
    update_type = str(update.get("update_type") or "")
    if update_type not in {"app_security", "app_updates", "app_update", "timelapse_update", "timelapse_pro_update"}:
        return True, "non-code update"

    if not security_cfg.get("artifact_verification_required", True):
        return True, "artifact verification disabled by policy"

    artifact = update.get("artifact")
    if not isinstance(artifact, dict):
        return False, "code update mangler signeret artifact"

    manifest = artifact.get("manifest")
    sha256 = artifact.get("sha256")
    actual_sha = artifact_manifest_sha(manifest)
    if not sha256 or not actual_sha or not hmac.compare_digest(str(sha256), actual_sha):
        return False, "artifact manifest SHA-256 matcher ikke"

    signer_fingerprint = artifact.get("signer_fingerprint")
    trusted = trusted_signer_fingerprints(security_cfg)
    if trusted and signer_fingerprint not in trusted:
        return False, "artifact signer er ikke trusted"
    if not trusted:
        return False, "ingen trusted release signers i Edge policy"

    if not artifact.get("signature"):
        return False, "artifact mangler signatur"

    return True, "artifact trust checks OK"


def ensure_edge_signing_key(base_dir: str | Path, device_id: str) -> dict[str, str]:
    """Create or load the Edge-local Ed25519 signing key.

    The private key never leaves the Edge. Headend receives only the OpenSSH
    public key and binds it to the CMDB device_id.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
        load_pem_private_key,
    )

    key_dir = Path(base_dir) / "keys"
    key_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(key_dir, 0o700)
    except OSError:
        pass
    private_path = key_dir / "edge_signing_ed25519.pem"
    public_path = key_dir / "edge_signing_ed25519.pub"

    if private_path.exists():
        private_key = load_pem_private_key(private_path.read_bytes(), password=None)
    else:
        private_key = Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            NoEncryption(),
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(private_path, flags, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(private_bytes)
        os.chmod(private_path, 0o600)

    public_key = private_key.public_key().public_bytes(
        Encoding.OpenSSH,
        PublicFormat.OpenSSH,
    ).decode("utf-8")
    public_path.write_text(f"{public_key} timelapse-edge-{device_id}\n")
    try:
        os.chmod(public_path, 0o644)
    except OSError:
        pass
    return {
        "public_key": public_key,
        "fingerprint": _fingerprint_material(public_key),
        "private_key_path": str(private_path),
        "public_key_path": str(public_path),
    }
