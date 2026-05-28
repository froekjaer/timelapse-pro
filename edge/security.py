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
import time
import uuid
from typing import Any


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def request_signature_headers(
    token: str | None,
    method: str,
    path: str,
    payload: dict | None = None,
) -> dict[str, str]:
    if not token:
        return {}
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    body = canonical_json(payload or {}) if payload else ""
    signed = "\n".join([method.upper(), path, timestamp, nonce, body])
    signature = hmac.new(token.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "X-TLP-Signature-Alg": "hmac-sha256-v1",
        "X-TLP-Timestamp": timestamp,
        "X-TLP-Nonce": nonce,
        "X-TLP-Signature": signature,
    }


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
