"""Mission Platform contracts — capability manifest v1 (ADR-002).

Strict, fail-closed validation: an unknown field, unknown capability, unknown
enum value, missing required field, or a quota above the operator-signed node
ceiling all REJECT. Nothing is silently ignored. No actuation capability exists
in v1 (safety gate for future OT payloads — adding one is a contract major bump).

Pure package — imports only its sibling contract module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .data import (
    PERSONAL_CLASSIFICATIONS,
    PERSONAL_DATA_KINDS,
    ChannelDecl,
    ChannelKind,
    Classification,
)

MANIFEST_VERSION = 1

# Capability vocabulary v1. NO actuation capabilities by design (safety gate).
KNOWN_CAPABILITIES = {"camera.usb", "gpio.read", "modbus.read", "sdr.rx"}

_TOP_FIELDS = {"manifest_version", "payload", "contracts", "capabilities",
               "quotas", "filesystem", "channels"}
_PAYLOAD_FIELDS = {"name", "version"}
_CONTRACT_FIELDS = {"control", "data"}
_QUOTA_FIELDS = {"cpu_pct", "mem_mb", "disk_mb", "net_kbps"}
_FS_FIELDS = {"readwrite"}
_CHANNEL_FIELDS = {"name", "kind", "classification", "retention_class"}


class ManifestRejected(Exception):
    """Fail-closed rejection; message states the exact reason."""


@dataclass(frozen=True)
class Quotas:
    cpu_pct: int
    mem_mb: int
    disk_mb: int
    net_kbps: int


@dataclass(frozen=True)
class Manifest:
    name: str
    version: str
    control_contract: str
    data_contract: str
    capabilities: frozenset
    quotas: Quotas
    fs_readwrite: tuple
    channels: tuple = field(default_factory=tuple)

    def channel(self, name: str) -> ChannelDecl:
        for ch in self.channels:
            if ch.name == name:
                return ch
        raise KeyError(name)


def _require_exact_fields(obj: Mapping[str, Any], allowed: set, where: str) -> None:
    unknown = set(obj) - allowed
    if unknown:
        raise ManifestRejected(f"{where}: unknown field(s) {sorted(unknown)} (fail closed)")
    missing = allowed - set(obj)
    if missing:
        raise ManifestRejected(f"{where}: missing required field(s) {sorted(missing)}")


def _contract_major(spec: str) -> int:
    head = str(spec).split(".", 1)[0]
    if not head.isdigit():
        raise ManifestRejected(f"contracts: cannot parse major from {spec!r}")
    return int(head)


def parse_manifest(doc: Mapping[str, Any]) -> Manifest:
    """Structural validation. Raises ManifestRejected on any deviation."""
    if not isinstance(doc, Mapping):
        raise ManifestRejected("manifest root must be a mapping")
    _require_exact_fields(doc, _TOP_FIELDS, "manifest")

    if doc["manifest_version"] != MANIFEST_VERSION:
        raise ManifestRejected(
            f"manifest_version {doc['manifest_version']!r} != {MANIFEST_VERSION}")

    _require_exact_fields(doc["payload"], _PAYLOAD_FIELDS, "payload")
    _require_exact_fields(doc["contracts"], _CONTRACT_FIELDS, "contracts")
    _require_exact_fields(doc["quotas"], _QUOTA_FIELDS, "quotas")
    _require_exact_fields(doc["filesystem"], _FS_FIELDS, "filesystem")

    caps = doc["capabilities"]
    if not isinstance(caps, Sequence) or isinstance(caps, (str, bytes)):
        raise ManifestRejected("capabilities must be a list")
    unknown_caps = set(caps) - KNOWN_CAPABILITIES
    if unknown_caps:
        raise ManifestRejected(f"unknown capability {sorted(unknown_caps)} (fail closed)")

    quotas = doc["quotas"]
    for k in _QUOTA_FIELDS:
        v = quotas[k]
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ManifestRejected(f"quotas.{k} must be a non-negative integer")

    channels = []
    seen = set()
    for ch in doc["channels"]:
        _require_exact_fields(ch, _CHANNEL_FIELDS, f"channel {ch.get('name', '?')!r}")
        try:
            kind = ChannelKind(ch["kind"])
            cls = Classification(ch["classification"])
        except ValueError as exc:
            raise ManifestRejected(f"channel {ch['name']!r}: {exc} (fail closed)") from exc
        if cls in PERSONAL_CLASSIFICATIONS and kind not in PERSONAL_DATA_KINDS:
            raise ManifestRejected(
                f"channel {ch['name']!r}: personal data forbidden on kind {kind.value} in v1")
        if ch["name"] in seen:
            raise ManifestRejected(f"duplicate channel {ch['name']!r}")
        seen.add(ch["name"])
        channels.append(ChannelDecl(ch["name"], kind, cls, ch["retention_class"]))

    return Manifest(
        name=doc["payload"]["name"],
        version=doc["payload"]["version"],
        control_contract=str(doc["contracts"]["control"]),
        data_contract=str(doc["contracts"]["data"]),
        capabilities=frozenset(caps),
        quotas=Quotas(**{k: quotas[k] for k in _QUOTA_FIELDS}),
        fs_readwrite=tuple(doc["filesystem"]["readwrite"]),
        channels=tuple(channels),
    )


def check_against_policy(
    manifest: Manifest,
    allowed_capabilities: frozenset,
    quota_ceilings: Quotas,
    supported_majors: Mapping[str, int],
) -> None:
    """Validate against the operator-signed node policy. Fail closed."""
    excess = manifest.capabilities - allowed_capabilities
    if excess:
        raise ManifestRejected(
            f"capability {sorted(excess)} not granted by node policy (fail closed)")
    for fld in _QUOTA_FIELDS:
        want, ceiling = getattr(manifest.quotas, fld), getattr(quota_ceilings, fld)
        if want > ceiling:
            raise ManifestRejected(
                f"quota {fld}={want} exceeds node ceiling {ceiling} (fail closed)")
    for contract, spec in (("control", manifest.control_contract),
                           ("data", manifest.data_contract)):
        if _contract_major(spec) != supported_majors[contract]:
            raise ManifestRejected(
                f"{contract} contract major {spec!r} unsupported "
                f"(platform supports {supported_majors[contract]}) (fail closed)")
