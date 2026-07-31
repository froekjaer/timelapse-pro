"""ADR-002 vertical slice: the timelapse payload wraps the REAL edge CameraBase
interface behind PayloadDriver and runs under the reference platform host.

Tests-only proof: a fake CameraBase (no gphoto2/hardware) exercises the exact
capture flow production will use. Also asserts the anti-coupling invariants
between contracts / platform_host / payloads on the actual source files.

CI runs with PYTHONPATH = repo:headend:edge, so `from camera.base import ...`
resolves via edge/.
"""
import ast
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "edge"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from contracts.control import Command, CommandRejected, PayloadPolicy  # noqa: E402
from contracts.manifest import Quotas  # noqa: E402
from platform_host.policy import load_verified_policy, sign_policy  # noqa: E402
from platform_host.supervisor import PayloadState, Supervisor, default_supported_majors  # noqa: E402
from payloads.timelapse.driver import TimelapsePayloadDriver  # noqa: E402
from camera.base import (  # noqa: E402
    CameraBase, CameraNotFoundError, CameraState, CameraStatus, CaptureResult,
)

NODE_KEY = b"vertical-slice-node-key"


# ── a fake CameraBase (implements the real abstract interface) ─────────────
class FakeCamera(CameraBase):
    def __init__(self, config=None, *, fail=False, present=True):
        super().__init__(config or {})
        self._fail = fail
        self._present = present
        self.captures = 0

    def connect(self):
        if not self._present:
            raise CameraNotFoundError("no camera")
        self._connected = True

    def disconnect(self):
        self._connected = False

    def capture_image(self, dest_dir: Path) -> CaptureResult:
        if self._fail:
            from camera.base import CaptureFailed
            raise CaptureFailed("simulated shutter failure")
        self.captures += 1
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        fp = dest / f"IMG_{self.captures:05d}.jpg"
        body = b"\xff\xd8\xff\xe0" + _dt.datetime.now(_dt.timezone.utc).isoformat().encode()
        fp.write_bytes(body)
        return CaptureResult(
            filepath=fp, timestamp=_dt.datetime.now(_dt.timezone.utc), filesize=len(body),
            sha256=hashlib.sha256(body).hexdigest(), camera_model="FakeCam Z30",
            driver_name="fake", exposure_time="1/250", aperture="f/8.0", iso=200,
            focus_mode="MF")

    def get_status(self) -> CameraStatus:
        return CameraStatus(state=CameraState.CONNECTED if self._connected else CameraState.DISCONNECTED,
                            model="FakeCam Z30", driver="fake", battery_pct=90,
                            storage_free_mb=1000, error_message=None)

    def health_check(self) -> bool:
        return self._present and not self._fail

    def supports_autofocus(self): return True
    def supports_liveview(self): return False
    def supports_remote_focus(self): return False
    def run_autofocus(self): return True
    def driver_name(self): return "fake"
    def supported_models(self): return ["FakeCam Z30"]


# ── fixtures ───────────────────────────────────────────────────────────────
@pytest.fixture()
def node_policy():
    doc = {
        "node_id": "TL-SLICE",
        "allowed_capabilities": ["camera.usb"],
        "quota_ceilings": {"cpu_pct": 80, "mem_mb": 1024, "disk_mb": 1024, "net_kbps": 0},
        "supported_contract_majors": default_supported_majors(),
    }
    return load_verified_policy(doc, sign_policy(doc, NODE_KEY), NODE_KEY)


@pytest.fixture()
def manifest_doc():
    return json.loads((REPO / "payloads" / "timelapse" / "manifest.json").read_text())


def _factory(camera, dest):
    def make(manifest, sink):
        return TimelapsePayloadDriver(camera, sink, dest)
    return make


# ── anti-coupling invariants on the real source files ──────────────────────
def _imported_roots(pkg_dir: Path):
    roots = set()
    for py in (REPO / pkg_dir).rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
    return roots


def test_platform_host_does_not_import_payloads():
    assert "payloads" not in _imported_roots(Path("platform_host"))


def test_timelapse_payload_does_not_import_platform_host():
    roots = _imported_roots(Path("payloads/timelapse"))
    assert "platform_host" not in roots
    assert "contracts" in roots  # it DOES use the seam


# ── end-to-end wrap of the real camera interface ───────────────────────────
def test_capture_flow_produces_classified_evidence(node_policy, manifest_doc, tmp_path):
    cam = FakeCamera()
    sup = Supervisor(node_policy, spool_root=tmp_path / "spool")
    sup.admit(manifest_doc, _factory(cam, tmp_path / "cam"))
    sup.configure_and_start("timelapse", PayloadPolicy(1, {"interval_s": 3600}))
    assert sup.state("timelapse") is PayloadState.RUNNING

    res = sup.command("timelapse", Command("capture_now"))
    assert res.ok and cam.captures >= 1

    spool = tmp_path / "spool" / "timelapse"
    metas = list(spool.glob("images-*.meta.json"))
    assert metas, "capture blob landed in spool"
    sidecar = json.loads(metas[0].read_text())
    assert sidecar["classification"] == "personal-images"
    assert sidecar["retention_class"] == "project-evidence-explicit-disposition"
    assert sidecar["attributes"]["camera_model"] == "FakeCam Z30"  # real metadata carried
    assert list(spool.glob("capture-metrics-*.meta.json")), "telemetry point landed"

    sup.stop("timelapse")
    assert sup.state("timelapse") is PayloadState.STOPPED
    assert not cam.connected  # camera released on stop


def test_absent_camera_is_handled(node_policy, manifest_doc, tmp_path):
    cam = FakeCamera(present=False)
    sup = Supervisor(node_policy, spool_root=tmp_path / "spool")
    sup.admit(manifest_doc, _factory(cam, tmp_path / "cam"))
    # start() calls camera.connect() which raises CameraNotFoundError -> propagates
    with pytest.raises(CameraNotFoundError):
        sup.configure_and_start("timelapse", PayloadPolicy(1, {"interval_s": 3600}))


def test_capture_failure_marks_health(node_policy, manifest_doc, tmp_path):
    cam = FakeCamera(fail=True)
    sup = Supervisor(node_policy, spool_root=tmp_path / "spool")
    sup.admit(manifest_doc, _factory(cam, tmp_path / "cam"))
    sup.configure_and_start("timelapse", PayloadPolicy(1, {"interval_s": 3600}))
    res = sup.command("timelapse", Command("capture_now"))
    assert not res.ok  # failure counted, not crashed
    stats = sup.command("timelapse", Command("get_stats"))
    assert stats.data["captures_failed"] >= 1
    sup.stop("timelapse")


def test_backpressure_drops_frame(node_policy, manifest_doc, tmp_path):
    doc = dict(manifest_doc)
    doc["quotas"] = dict(doc["quotas"], disk_mb=0)  # zero disk -> immediate backpressure
    cam = FakeCamera()
    sup = Supervisor(node_policy, spool_root=tmp_path / "spool")
    sup.admit(doc, _factory(cam, tmp_path / "cam"))
    sup.configure_and_start("timelapse", PayloadPolicy(1, {"interval_s": 3600}))
    res = sup.command("timelapse", Command("capture_now"))
    assert not res.ok  # frame dropped per declared strategy
    sup.stop("timelapse")


def test_unknown_command_rejected(node_policy, manifest_doc, tmp_path):
    cam = FakeCamera()
    sup = Supervisor(node_policy, spool_root=tmp_path / "spool")
    sup.admit(manifest_doc, _factory(cam, tmp_path / "cam"))
    sup.configure_and_start("timelapse", PayloadPolicy(1, {"interval_s": 3600}))
    with pytest.raises(CommandRejected):
        sup.command("timelapse", Command("format_disk"))
    sup.stop("timelapse")
