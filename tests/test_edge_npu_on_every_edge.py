"""NPU QA runs on every Edge (Peter 2026-10-05: "Lad os få NPU til at virke på begge").

Bundled portable wrapper + model in every release/image; the result is recorded
with every capture in "shadow" mode (CPU verdict stands) until a model passes
real-world acceptance.
"""
import hashlib
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "edge"))

# Loaded by path: headend/ai and edge/ai are both a package called "ai".
def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


npu_quality = _load("edge_npu_quality_under_test", "edge/ai/npu_quality.py")
QualityChecker = _load("edge_quality_under_test", "edge/capture/quality.py").QualityChecker

BIN = ROOT / "edge/npu_viplite/bin/edge_qa_viplite"
MODEL = ROOT / "edge/ai/models/edge_qa_edge_cnn_mini.nb"


def test_bundled_artifacts_match_recorded_provenance():
    build = (ROOT / "edge/npu_viplite/bin/BUILD.txt").read_text(encoding="utf-8")
    assert hashlib.sha256(BIN.read_bytes()).hexdigest() in build
    assert hashlib.sha256(MODEL.read_bytes()).hexdigest() == "d98274bdf7bf36745300cbf8da4ebc2e07a1c95f62b6c0e21b86f247ca8eda24"
    assert BIN.read_bytes()[:4] == b"\x7fELF"


def test_release_manifest_ships_them():
    main = (ROOT / "headend/main.py").read_text(encoding="utf-8")
    assert 'root / "edge" / "ai",' in main and 'root / "edge" / "npu_viplite",' in main


def test_adapter_defaults_to_bundled_model_and_wrapper_in_shadow():
    a = npu_quality.NpuQualityAdapter({"quality": {"edge_ai": {"enabled": True, "model_path": "", "vendor_binary": ""}}})
    st = a.status()
    assert st["model_path"] == str(MODEL) and st["model_present"]
    assert st["vendor_binary"].startswith(str(BIN)) and "--input-layout nchw_rgb --input-dtype uint8" in st["vendor_binary"]
    assert a.influence == "shadow"
    override = npu_quality.NpuQualityAdapter({"quality": {"edge_ai": {"model_path": "/x.nb", "npu_influence": "merge"}}})
    assert override.status()["model_path"] == "/x.nb" and override.influence == "merge"
    assert npu_quality.NpuQualityAdapter({"quality": {"edge_ai": {"npu_influence": "bogus"}}}).influence == "shadow"


class _FakeNpu:
    def __init__(self, influence):
        self.influence = influence

    def analyse(self, _path):
        return {"engine": "edge_qa_viplite_aw_nn_v1", "available": True, "accepted": True,
                "label": "white_balance_cast", "probable_cause": "white_balance_cast", "confidence": 0.95, "is_anomaly": True}

    def status(self):
        return {"enabled": True}


def _report(tmp_path, influence):
    import numpy as np
    import cv2
    img = tmp_path / "ok.jpg"
    rng = np.random.default_rng(1)
    cv2.imwrite(str(img), (rng.random((240, 320, 3)) * 255).astype("uint8"))
    qc = QualityChecker({"quality": {"edge_ai": {"enabled": True}}})
    qc._npu = _FakeNpu(influence)
    return qc.qa_report(img) if hasattr(qc, "qa_report") else qc.check(img).as_dict()


def test_shadow_records_npu_but_cpu_verdict_stands(tmp_path):
    shadow = _report(tmp_path, "shadow")
    assert shadow["npu"]["label"] == "white_balance_cast" and shadow["npu"]["influence"] == "shadow"
    assert shadow.get("probable_cause") != "white_balance_cast"
    merged = _report(tmp_path, "merge")
    assert merged.get("probable_cause") == "white_balance_cast"


def test_runner_feeds_raw_rgb_and_heals_exec_bit(tmp_path):
    spec = importlib.util.spec_from_file_location("runner", ROOT / "edge/tools/edge_qa_npu_runner.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    import numpy as np
    import cv2
    img = tmp_path / "a.jpg"
    cv2.imwrite(str(img), np.zeros((100, 150, 3), dtype="uint8"))
    raw = runner._write_rgb_input(img)
    assert raw.stat().st_size == 224 * 224 * 3
    raw.unlink()
    exe = tmp_path / "wrapper"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o644)
    runner._ensure_executable(exe)
    assert os.access(exe, os.X_OK)
    src = (ROOT / "edge/tools/edge_qa_npu_runner.py").read_text(encoding="utf-8")
    assert '"--input-raw", str(raw)' in src


def test_wrapper_source_is_portable():
    cpp = (ROOT / "edge/npu_viplite/edge_qa_viplite.cpp").read_text(encoding="utf-8")
    assert '"--input-raw"' in cpp
    assert cpp.index("#ifdef TIMELAPSE_WITH_OPENCV") < cpp.index("#include <opencv2/imgcodecs.hpp>")
    build = (ROOT / "edge/tools/build_edge_qa_viplite.sh").read_text(encoding="utf-8")
    assert "opencv" not in build.lower().replace("no opencv", "")
    assert (ROOT / "edge/npu_viplite/vendor/libawnn_viplite/awnn_quantize.c").is_file()


def test_baseline_protects_audit_logs_from_ramlog(tmp_path):
    spec = importlib.util.spec_from_file_location("baseline", ROOT / "edge/scripts/timelapse_system_baseline.py")
    b = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b)
    (tmp_path / "etc/default").mkdir(parents=True)
    vendor = "ENABLED=true\nUSE_RSYNC=true\n#XTRA_RSYNC_TO=(--delete)\nXTRA_RSYNC_FROM=()\nXTRA_RSYNC_FROM=()\n"
    (tmp_path / b.RAMLOG_DEFAULTS).write_text(vendor)
    assert b.ramlog_exclude(tmp_path)["status"] == "changed"
    assert b.ramlog_exclude(tmp_path)["status"] == "ok"
    text = (tmp_path / b.RAMLOG_DEFAULTS).read_text()
    assert text.rstrip().endswith("XTRA_RSYNC_FROM=(--exclude=/timelapse/)")
    assert "XTRA_RSYNC_TO=(--exclude=/timelapse/)" in text
    assert ("ramlog", b.ramlog_exclude) in b.STEPS


def test_unrunnable_wrapper_falls_back_to_cpu(tmp_path):
    spec = importlib.util.spec_from_file_location("runner2", ROOT / "edge/tools/edge_qa_npu_runner.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    import numpy as np
    import cv2
    img = tmp_path / "a.jpg"
    cv2.imwrite(str(img), np.full((100, 150, 3), 128, dtype="uint8"))
    bogus = tmp_path / "not-arm"
    bogus.write_bytes(b"\x7fELF\x00garbage")
    out = runner.analyse(img, MODEL, str(bogus))
    assert out["engine"] == "edge_npu_contract_cpu_fallback"
