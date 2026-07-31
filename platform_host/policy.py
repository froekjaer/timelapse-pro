"""Operator-signed node policy (HMAC-SHA256 for the slice; production uses
the existing asymmetric signing chain from the source OTA/config trust model).
Fail closed: missing/invalid signature => PolicyUnverified.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Mapping

from contracts.manifest import Quotas


class PolicyUnverified(Exception):
    """Signature absent or invalid — the policy must not be used."""


@dataclass(frozen=True)
class NodePolicy:
    """What the operator allows THIS node to grant to payloads."""

    node_id: str
    allowed_capabilities: frozenset[str]
    quota_ceilings: Quotas
    supported_contract_majors: Mapping[str, int]


def _canonical(doc: Mapping[str, Any]) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()


def sign_policy(doc: Mapping[str, Any], key: bytes) -> str:
    return hmac.new(key, _canonical(doc), hashlib.sha256).hexdigest()


def load_verified_policy(doc: Mapping[str, Any], signature: str, key: bytes) -> NodePolicy:
    expected = sign_policy(doc, key)
    if not signature or not hmac.compare_digest(expected, signature):
        raise PolicyUnverified("node policy signature invalid or missing (fail closed)")
    return NodePolicy(
        node_id=doc["node_id"],
        allowed_capabilities=frozenset(doc["allowed_capabilities"]),
        quota_ceilings=Quotas(**doc["quota_ceilings"]),
        supported_contract_majors=dict(doc["supported_contract_majors"]),
    )
