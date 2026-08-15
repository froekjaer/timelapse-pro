"""Authenticated Edge SSH host identity evidence API."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import EdgeSshHostIdentityEvidence


class SshHostIdentityEvidenceRequest(BaseModel):
    device_id: str
    evidence_source: Optional[str] = "authenticated_edge_report"
    evidence: dict


def _parse_edge_iso_datetime(value: str | None, now_utc: Callable):
    if not value:
        return now_utc()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return now_utc()


def create_ssh_host_identity_router(
    verify_device_token: Callable,
    get_db: Callable,
    now_utc: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/api/trust", tags=["trust-evidence"])

    @router.post("/ssh-host-identity/{device_id}")
    def report_ssh_host_identity(
        device_id: str,
        req: SshHostIdentityEvidenceRequest,
        _auth: None = Depends(verify_device_token),
        db: Session = Depends(get_db),
    ):
        """Store authenticated read-only SSH server host-key evidence.

        This records what the already authenticated Edge says its SSH public host
        keys are. It must not update known_hosts or mark keys trusted.
        """
        if req.device_id != device_id:
            raise HTTPException(status_code=400, detail="device_id mismatch")
        evidence = req.evidence if isinstance(req.evidence, dict) else {}
        if evidence.get("device_id") and evidence.get("device_id") != device_id:
            raise HTTPException(status_code=400, detail="evidence device_id mismatch")
        if req.evidence_source != "authenticated_edge_report":
            raise HTTPException(status_code=400, detail="unsupported evidence_source")

        release = evidence.get("software") if isinstance(evidence.get("software"), dict) else {}
        observed_at = _parse_edge_iso_datetime(evidence.get("observed_at"), now_utc)
        inserted = 0
        for item in evidence.get("keys") or []:
            if not isinstance(item, dict) or item.get("status") != "observed":
                continue
            fingerprint = str(item.get("fingerprint_sha256") or "")
            key_type = str(item.get("key_type") or "")
            public_key_path = str(item.get("path") or "")
            if not fingerprint.startswith("SHA256:") or not key_type or not public_key_path.endswith(".pub"):
                raise HTTPException(status_code=400, detail="invalid SSH host-key evidence")
            db.add(EdgeSshHostIdentityEvidence(
                device_id=device_id,
                key_type=key_type,
                fingerprint=fingerprint,
                public_key_path=public_key_path,
                hostname=evidence.get("hostname"),
                observed_at=observed_at,
                evidence_source="authenticated_edge_report",
                software_version=release.get("version"),
                source_commit=release.get("source_commit"),
                release_artifact_id=release.get("artifact_id"),
                status="observed",
                trusted_state="untrusted_observed",
                raw_evidence_json=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
            ))
            inserted += 1
        if inserted == 0:
            raise HTTPException(status_code=400, detail="no observed SSH host-key fingerprints")
        db.commit()
        return {
            "ok": True,
            "device_id": device_id,
            "observed": inserted,
            "trusted_state": "untrusted_observed",
        }

    return router
