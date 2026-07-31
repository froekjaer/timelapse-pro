"""SpoolDataSink — the platform's data-plane implementation for the slice.

Enforces: only declared channels (fail closed), kind matching, disk quota
with Backpressure, classification recorded on every object (GDPR mechanism).
Objects land in a local spool directory exactly like the edge agent's
forwarder queue would consume.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path

from contracts.data import (
    Backpressure,
    BlobMeta,
    ChannelKind,
    DataSink,
    Event,
    PutReceipt,
    TimeseriesPoint,
    UndeclaredChannel,
)
from contracts.manifest import Manifest


class SpoolDataSink(DataSink):
    def __init__(self, manifest: Manifest, spool_dir: Path) -> None:
        self._manifest = manifest
        self._dir = spool_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._quota_bytes = manifest.quotas.disk_mb * 1024 * 1024
        self._used = 0

    # -- enforcement helpers -------------------------------------------------
    def _declared(self, channel: str, kind: ChannelKind):
        try:
            decl = self._manifest.channel(channel)
        except KeyError:
            raise UndeclaredChannel(
                f"channel {channel!r} not declared in manifest (fail closed)")
        if decl.kind is not kind:
            raise UndeclaredChannel(
                f"channel {channel!r} is {decl.kind.value}, not {kind.value}")
        return decl

    def _reserve(self, nbytes: int) -> None:
        if self._used + nbytes > self._quota_bytes:
            raise Backpressure(retry_after_s=30.0)
        self._used += nbytes

    def _write(self, channel: str, suffix: str, blob: bytes, sidecar: dict) -> PutReceipt:
        object_id = uuid.uuid4().hex
        base = self._dir / f"{channel}-{object_id}"
        self._reserve(len(blob) + 512)
        base.with_suffix(suffix).write_bytes(blob)
        base.with_suffix(".meta.json").write_text(json.dumps(sidecar, sort_keys=True))
        return PutReceipt(channel=channel, object_id=object_id)

    # -- DataSink ------------------------------------------------------------
    def put_blob(self, channel: str, payload: bytes, meta: BlobMeta) -> PutReceipt:
        decl = self._declared(channel, ChannelKind.BLOB)
        sidecar = {"classification": decl.classification.value,
                   "retention_class": decl.retention_class, **asdict(meta)}
        return self._write(channel, ".bin", payload, sidecar)

    def put_point(self, channel: str, point: TimeseriesPoint) -> PutReceipt:
        decl = self._declared(channel, ChannelKind.TIMESERIES)
        sidecar = {"classification": decl.classification.value,
                   "retention_class": decl.retention_class, **asdict(point)}
        return self._write(channel, ".point.json",
                           json.dumps(asdict(point)).encode(), sidecar)

    def put_event(self, channel: str, event: Event) -> PutReceipt:
        decl = self._declared(channel, ChannelKind.EVENT)
        sidecar = {"classification": decl.classification.value,
                   "retention_class": decl.retention_class, **asdict(event)}
        return self._write(channel, ".event.json",
                           json.dumps(asdict(event)).encode(), sidecar)
