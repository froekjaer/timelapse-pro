"""Mission Platform contracts — data plane v1 (ADR-002).

Three channel kinds cover every named future payload (timelapse = blob +
timeseries; waterworks/energy = timeseries + event; maritime/SDR = all three).
Every channel carries a data classification and a retention class so the
platform can enforce GDPR retention as a mechanism, not documentation.

Pure package — imports nothing from headend/ or edge/.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

DATA_CONTRACT_VERSION = "1.0.0"


class ChannelKind(str, Enum):
    BLOB = "blob"
    TIMESERIES = "timeseries"
    EVENT = "event"


class Classification(str, Enum):
    PERSONAL_IMAGES = "personal-images"
    PERSONAL_OTHER = "personal-other"
    PROCESS_TELEMETRY = "process-telemetry"
    OPERATIONAL = "operational"
    PUBLIC = "public"


PERSONAL_CLASSIFICATIONS = {Classification.PERSONAL_IMAGES, Classification.PERSONAL_OTHER}
# In v1, personal data may only travel on blob channels (privacy architecture).
PERSONAL_DATA_KINDS = {ChannelKind.BLOB}


class DataPlaneError(Exception):
    """Base for data-plane failures."""


class Backpressure(DataPlaneError):
    """Spool/transport full. Payload applies its declared drop/buffer strategy."""

    def __init__(self, retry_after_s: float) -> None:
        super().__init__(f"backpressure, retry after {retry_after_s}s")
        self.retry_after_s = retry_after_s


class UndeclaredChannel(DataPlaneError):
    """Write to a channel not declared in the manifest (fail closed)."""


@dataclass(frozen=True)
class ChannelDecl:
    name: str
    kind: ChannelKind
    classification: Classification
    retention_class: str


@dataclass(frozen=True)
class BlobMeta:
    content_type: str
    captured_at: str  # ISO 8601 UTC
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TimeseriesPoint:
    ts: str
    value: float
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Event:
    ts: str
    kind: str
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PutReceipt:
    channel: str
    object_id: str


class DataSink(ABC):
    """Provided BY the platform TO the payload — the payload's only data exit."""

    @abstractmethod
    def put_blob(self, channel: str, payload: bytes, meta: BlobMeta) -> PutReceipt: ...

    @abstractmethod
    def put_point(self, channel: str, point: TimeseriesPoint) -> PutReceipt: ...

    @abstractmethod
    def put_event(self, channel: str, event: Event) -> PutReceipt: ...
