"""
TimeLapse Pro Edge security helpers.

Provides transitional mutual-auth request signing and artifact trust checks.
Edge still authenticates with its Bearer token, but signed requests allow
Headend to validate signal integrity and replay metadata while the fleet moves
towards per-device signing keys or mTLS.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
import tempfile
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


def _trusted_signer(security_cfg: dict, signer_fingerprint: str | None) -> dict | None:
    if not signer_fingerprint:
        return None
    for signer in security_cfg.get("trusted_release_signers") or []:
        if isinstance(signer, dict) and hmac.compare_digest(
            str(signer.get("fingerprint") or ""), str(signer_fingerprint)
        ):
            return signer
    return None


def _fingerprint_material(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalise_gpg_fingerprint(value: str | None) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch in "0123456789ABCDEF")


def _public_key_gpg_fingerprint(public_key: str, homedir: str) -> str | None:
    """Inspect an armored key without trusting/importing it and return its primary fingerprint."""
    key_path = Path(homedir) / "release-public-key.asc"
    key_path.write_text(public_key, encoding="utf-8")
    result = subprocess.run(
        [
            "gpg", "--batch", "--no-tty", "--homedir", homedir,
            "--with-colons", "--import-options", "show-only", "--import", str(key_path),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if parts and parts[0] == "fpr" and len(parts) > 9:
            return _normalise_gpg_fingerprint(parts[9])
    return None


def _verify_openpgp_manifest_signature(
    manifest: dict,
    signature: str,
    signer: dict,
) -> tuple[bool, str]:
    """Verify a detached OpenPGP signature against the pinned signer public key.

    The temporary GNUPGHOME contains only the public key distributed in the
    Edge trust policy. No host/user GPG keyring or network key discovery is used.
    """
    public_key = str(signer.get("public_key") or "").strip()
    expected_gpg_fingerprint = _normalise_gpg_fingerprint(signer.get("gpg_fingerprint"))
    expected_material_fingerprint = str(signer.get("fingerprint") or "")
    if not public_key or not expected_gpg_fingerprint or not expected_material_fingerprint:
        return False, "trusted release signer mangler pinned public key/fingerprint"
    if not hmac.compare_digest(_fingerprint_material(public_key), expected_material_fingerprint):
        return False, "trusted release signer public-key fingerprint matcher ikke policy"
    if not signature.strip().startswith("-----BEGIN PGP SIGNATURE-----"):
        return False, "artifact signatur er ikke en OpenPGP detached signatur"

    try:
        with tempfile.TemporaryDirectory(prefix="tlp-gpg-verify-") as homedir:
            os.chmod(homedir, 0o700)
            actual_gpg_fingerprint = _public_key_gpg_fingerprint(public_key, homedir)
            if not actual_gpg_fingerprint or not hmac.compare_digest(
                actual_gpg_fingerprint, expected_gpg_fingerprint
            ):
                return False, "trusted release signer GPG fingerprint matcher ikke public key"

            key_path = Path(homedir) / "release-public-key.asc"
            manifest_path = Path(homedir) / "manifest.json"
            signature_path = Path(homedir) / "manifest.asc"
            manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
            signature_path.write_text(signature, encoding="utf-8")

            imported = subprocess.run(
                ["gpg", "--batch", "--no-tty", "--homedir", homedir, "--import", str(key_path)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if imported.returncode != 0:
                return False, "trusted release signer public key kunne ikke importeres"

            verified = subprocess.run(
                [
                    "gpg", "--batch", "--no-tty", "--homedir", homedir,
                    "--status-fd", "1", "--verify", str(signature_path), str(manifest_path),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if verified.returncode != 0:
                return False, "artifact OpenPGP signaturverifikation fejlede"

            valid_fingerprints = []
            for line in verified.stdout.splitlines():
                if line.startswith("[GNUPG:] VALIDSIG "):
                    fields = line.split()
                    if len(fields) >= 3:
                        valid_fingerprints.append(_normalise_gpg_fingerprint(fields[2]))
            if expected_gpg_fingerprint not in valid_fingerprints:
                return False, "artifact signatur er ikke lavet af den pinned release signer"
            return True, "OpenPGP signature verified"
    except FileNotFoundError:
        return False, "gpg mangler på Edge; artifact verification fail-closed"
    except (OSError, subprocess.SubprocessError):
        return False, "OpenPGP verifiering kunne ikke udføres; artifact afvist"


def verify_update_artifact(update: dict, security_cfg: dict) -> tuple[bool, str]:
    """Validate code/OS artifacts cryptographically before Edge installation.

    Code updates always require an immutable manifest hash, a pinned release
    signer public key and a valid detached OpenPGP signature over the canonical
    manifest. A policy flag cannot disable this gate for executable updates.
    """
    update_type = str(update.get("update_type") or "")
    code_update_types = {
        "app_security",
        "app_updates",
        "app_update",
        "timelapse_update",
        "timelapse_pro_update",
        "timelapse_security",
        "timelapse_pro_security",
        "application_security",
        "application_update",
        "application_updates",
        "dependency_security",
        "dependency_updates",
        "third_party_security",
        "third_party_updates",
        "os_security",
        "os_updates",
    }
    if update_type not in code_update_types:
        return True, "non-code update"

    if not security_cfg.get("artifact_verification_required", True):
        return False, "artifact verification kan ikke deaktiveres for code/OS updates"

    artifact = update.get("artifact")
    if not isinstance(artifact, dict):
        return False, "code update mangler signeret artifact"

    manifest = artifact.get("manifest")
    if not isinstance(manifest, dict):
        return False, "artifact manifest mangler eller er ugyldigt"
    sha256 = artifact.get("sha256")
    actual_sha = artifact_manifest_sha(manifest)
    if not sha256 or not actual_sha or not hmac.compare_digest(str(sha256), actual_sha):
        return False, "artifact manifest SHA-256 matcher ikke"

    signed_by = str(artifact.get("signed_by") or "").strip()
    signature = str(artifact.get("signature") or "").strip()
    if signed_by == "system-hash" or signature.startswith("sha256:"):
        return False, "hash-only artifact er ikke kryptografisk release-signeret"
    if not signature:
        return False, "artifact mangler signatur"

    signer_fingerprint = str(artifact.get("signer_fingerprint") or "")
    signer = _trusted_signer(security_cfg, signer_fingerprint)
    if signer is None:
        return False, "artifact signer er ikke trusted"

    verified, verify_reason = _verify_openpgp_manifest_signature(manifest, signature, signer)
    if not verified:
        return False, verify_reason

    artifact_type = str(artifact.get("artifact_type") or "")
    if update_type in {"os_security", "os_updates"}:
        if artifact_type != "os":
            return False, "OS update kræver artifact_type=os"
        if manifest.get("schema") != "timelapse.os_update_artifact.v1":
            return False, "OS artifact manifest schema er ugyldigt"
        if manifest.get("distribution_model") != "headend_signed_offline_os_bundle_edge_pull":
            return False, "OS artifact skal være offline Headend bundle"

    return True, f"artifact trust checks OK; {verify_reason}"


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