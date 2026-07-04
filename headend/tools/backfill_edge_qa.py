#!/usr/bin/env python3
"""
Backfill Edge QA analysis for historical captures.

Runs the same deterministic Edge QA path as the edge agent
(`edge.capture.quality.QualityChecker.qa_report`) against original images,
then writes:

- captures.quality_flag / quality_passed / blur_score / brightness_mean
- captures.ai_result.edge_ai
- sidecar JSON `edge_qa`

The tool is intentionally dry-run first and can be scoped by device, site,
camera, date and limit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_, text

HEADEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HEADEND_ROOT.parent
for _path in (str(HEADEND_ROOT), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from database import Capture, Device, SessionLocal  # noqa: E402
from ai.ai_models import CaptureModelResult  # noqa: E402
from ai.model_results import ENGINE_EDGE_CV, upsert_capture_model_result  # noqa: E402

_TLS = threading.local()


def _setting(db, key: str, fallback: str = "") -> str:
    try:
        row = db.execute(text("SELECT value FROM settings WHERE key=:k"), {"k": key}).fetchone()
        if row and row[0] not in (None, ""):
            return str(row[0])
    except Exception:
        pass
    return fallback


def _roots(db) -> list[Path]:
    roots: list[Path] = []
    primary = _setting(db, "sftp_base", os.getenv("SFTP_BASE", "/Volumes/data-fast"))
    if primary:
        roots.append(Path(primary).expanduser())
    raw = _setting(db, "sftp_legacy_roots", os.getenv("SFTP_LEGACY_ROOTS", ""))
    for item in str(raw or "").replace("\n", ",").split(","):
        item = item.strip()
        if item:
            roots.append(Path(item).expanduser())
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            deduped.append(root)
    return deduped


def _date_parts(filename: str) -> tuple[str, str, str] | None:
    import re

    m = re.search(r"_(\d{4})(\d{2})(\d{2})_\d{6}\.\w+$", filename)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)


def _image_from_sidecar(capture: Capture) -> Path | None:
    if not capture.sidecar_path:
        return None
    sidecar = Path(capture.sidecar_path)
    for candidate in (
        sidecar.with_suffix(".jpg"),
        sidecar.with_suffix(".jpeg"),
        sidecar.with_suffix(".JPG"),
        sidecar.with_suffix(".JPEG"),
    ):
        if candidate.exists():
            return candidate
    return None


def _image_from_sidecar_path(sidecar_path: str | None) -> Path | None:
    if not sidecar_path:
        return None
    sidecar = Path(sidecar_path)
    for candidate in (
        sidecar.with_suffix(".jpg"),
        sidecar.with_suffix(".jpeg"),
        sidecar.with_suffix(".JPG"),
        sidecar.with_suffix(".JPEG"),
    ):
        if candidate.exists():
            return candidate
    return None


def _find_image_in_roots(roots: list[Path], device_id: str, filename: str, sidecar_path: str | None = None) -> Path | None:
    direct = _image_from_sidecar_path(sidecar_path)
    if direct:
        return direct

    parts = _date_parts(filename or "")
    for root in roots:
        if parts:
            yyyy, mm, dd = parts
            patterns = [
                f"*/*/*/{yyyy}/{mm}/{dd}/{filename}",
                f"*/*/{yyyy}/{mm}/{dd}/{filename}",
                f"{device_id}/{yyyy}/{mm}/{dd}/{filename}",
                f"timelapse-incoming/*/data/*/*/*/{yyyy}/{mm}/{dd}/{filename}",
                f"timelapse-incoming/*/data/*/*/{yyyy}/{mm}/{dd}/{filename}",
            ]
            for pattern in patterns:
                matches = list(root.glob(pattern))
                if matches:
                    return matches[0]
        flat = root / str(device_id) / str(filename)
        if flat.exists():
            return flat
    return None


def _find_image(db, capture: Capture) -> Path | None:
    return _find_image_in_roots(_roots(db), str(capture.device_id), str(capture.filename), capture.sidecar_path)


def _config(mode: str, runner: str, model: str, vendor_binary: str) -> dict[str, Any]:
    return {
        "quality": {
            "check_enabled": True,
            "blur_threshold": 80,
            "dark_threshold": 25,
            "bright_threshold": 230,
            "adaptive_exposure": {
                "enabled": mode not in {"off", "monitor"},
                "target_brightness": 118,
                "brightness_tolerance": 32,
                "step_ev": 0.3,
                "min_ev": -2.0,
                "max_ev": 2.0,
            },
            "edge_ai": {
                "enabled": mode != "off",
                "mode": mode,
                "prefer_npu": mode == "npu_first",
                "runner": runner,
                "model_path": model,
                "vendor_binary": vendor_binary,
            },
        }
    }


def _edge_payload(report: dict[str, Any], image_path: Path) -> dict[str, Any]:
    opt = report.get("autonomous_optimizer") or {}
    edge_tags = [str(tag).strip().lower() for tag in (opt.get("tags") or []) if str(tag).strip()]
    score = opt.get("score")
    optimizer_score = None
    if isinstance(score, dict):
        try:
            optimizer_score = float(score.get("overall")) / 100.0
        except Exception:
            optimizer_score = None
    elif score is not None:
        try:
            raw_score = float(score)
            optimizer_score = raw_score if raw_score <= 1.0 else raw_score / 100.0
        except Exception:
            optimizer_score = None
    return {
        "schema": "timelapse.edge_qa.backfill.v1",
        "source": "edge",
        "backfilled_at": datetime.now(timezone.utc).isoformat(),
        "image_path": str(image_path),
        "engine": report.get("engine"),
        "flag": report.get("flag"),
        "passed": report.get("passed"),
        "is_anomaly": report.get("is_anomaly"),
        "probable_cause": report.get("probable_cause"),
        "confidence": report.get("confidence"),
        "recommended_action": report.get("recommended_action"),
        "blur_score": report.get("blur_score"),
        "brightness_mean": report.get("brightness_mean"),
        "blur_threshold": report.get("blur_threshold"),
        "dark_threshold": report.get("dark_threshold"),
        "bright_threshold": report.get("bright_threshold"),
        "cv_features": report.get("cv_features") or {},
        "npu": report.get("npu") or {},
        "autonomous_optimizer": opt,
        "tags": list(dict.fromkeys(edge_tags)),
        "optimizer_score": optimizer_score,
        "control_plan": opt.get("control_plan"),
        "recommendations": opt.get("recommendations") or [],
    }


def _write_sidecar(image_path: Path, payload: dict[str, Any]) -> bool:
    sidecar = image_path.with_suffix(".json")
    data: dict[str, Any] = {}
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["edge_qa"] = payload
    data.setdefault("timelapse_pro", {})
    data["timelapse_pro"]["edge_qa_backfilled_at"] = payload["backfilled_at"]
    sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def _merge_ai_result(existing_raw: str | None, payload: dict[str, Any]) -> str:
    existing: dict[str, Any] = {}
    if existing_raw:
        try:
            parsed = json.loads(existing_raw)
            if isinstance(parsed, dict):
                existing = parsed
        except Exception:
            existing = {}
    if not existing:
        existing = {
            "model": payload.get("engine") or "edge_cv_v1",
            "quality_flag": payload.get("flag"),
            "quality_ok": bool(payload.get("passed")),
            "probable_cause": payload.get("probable_cause"),
            "confidence": payload.get("confidence"),
            "is_anomaly": payload.get("is_anomaly"),
        }
    existing["edge_ai"] = payload
    return json.dumps(existing, ensure_ascii=False)


def _query(db, args):
    q = db.query(Capture)
    if args.device_id:
        q = q.filter(Capture.device_id == args.device_id)
    if args.site or args.camera:
        q = q.join(Device, Device.device_id == Capture.device_id)
        if args.site:
            q = q.filter(Device.site_name.ilike(f"%{args.site}%"))
        if args.camera:
            q = q.filter(or_(Device.camera_name.ilike(f"%{args.camera}%"), Capture.filename.ilike(f"%{args.camera}%")))
    if args.since:
        q = q.filter(Capture.captured_at >= datetime.fromisoformat(args.since))
    if args.until:
        q = q.filter(Capture.captured_at < datetime.fromisoformat(args.until))
    if args.only_missing_edge:
        q = q.outerjoin(
            CaptureModelResult,
            and_(
                CaptureModelResult.capture_id == Capture.id,
                CaptureModelResult.engine == ENGINE_EDGE_CV,
            ),
        ).filter(CaptureModelResult.id.is_(None))
    q = q.order_by(Capture.captured_at.asc().nullslast(), Capture.id.asc())
    if args.limit:
        q = q.limit(args.limit)
    return q


def _capture_ref(capture: Capture) -> dict[str, Any]:
    return {
        "id": capture.id,
        "device_id": str(capture.device_id or ""),
        "filename": str(capture.filename or ""),
        "captured_at": capture.captured_at.isoformat() if capture.captured_at else None,
        "sidecar_path": capture.sidecar_path,
    }


def _analyse_ref(ref: dict[str, Any], roots: list[Path], config: dict[str, Any]) -> dict[str, Any]:
    from edge.capture.quality import QualityChecker

    checker = getattr(_TLS, "checker", None)
    if checker is None:
        checker = QualityChecker(config)
        _TLS.checker = checker
    image = _find_image_in_roots(roots, ref["device_id"], ref["filename"], ref.get("sidecar_path"))
    if not image:
        return {**ref, "missing_file": True}
    report = checker.qa_report(image)
    payload = _edge_payload(report, image)
    return {**ref, "image": str(image), "report": report, "edge_ai": payload}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", default="")
    parser.add_argument("--site", default="")
    parser.add_argument("--camera", default="")
    parser.add_argument("--since", default="")
    parser.add_argument("--until", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--commit-every", type=int, default=100)
    parser.add_argument("--mode", default="assist", choices=["off", "monitor", "assist", "autonomous", "npu_first", "lab"])
    parser.add_argument("--runner", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--vendor-binary", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-missing-edge", action="store_true")
    parser.add_argument("--out", default="")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    from edge.capture.quality import QualityChecker

    config = _config(args.mode, args.runner, args.model, args.vendor_binary)
    checker = QualityChecker(config)
    db = SessionLocal()
    out_fh = Path(args.out).open("w", encoding="utf-8") if args.out else None
    stats = {"seen": 0, "updated": 0, "missing_file": 0, "errors": 0, "anomalies": 0}
    by_cause: dict[str, int] = {}
    started = time.time()
    executor: ThreadPoolExecutor | None = None
    try:
        rows = _query(db, args).all()
        total = len(rows)
        if args.workers > 1:
            roots = _roots(db)
            refs = [_capture_ref(capture) for capture in rows]
            executor = ThreadPoolExecutor(max_workers=args.workers)
            futures = [executor.submit(_analyse_ref, ref, roots, config) for ref in refs]
            iterator = enumerate(as_completed(futures), start=1)
        else:
            def _sequential():
                for capture in rows:
                    image = _find_image(db, capture)
                    if not image:
                        yield _capture_ref(capture) | {"missing_file": True}
                        continue
                    report = checker.qa_report(image)
                    yield _capture_ref(capture) | {
                        "image": str(image),
                        "report": report,
                        "edge_ai": _edge_payload(report, image),
                    }

            iterator = enumerate(_sequential(), start=1)

        for idx, item in iterator:
            if hasattr(item, "result"):
                try:
                    item = item.result()
                except Exception as exc:
                    stats["seen"] += 1
                    stats["errors"] += 1
                    if out_fh:
                        out_fh.write(json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n")
                    continue
            stats["seen"] += 1
            if item.get("missing_file"):
                stats["missing_file"] += 1
                continue
            try:
                report = item["report"]
                payload = item["edge_ai"]
                image = Path(item["image"])
                cause = str(payload.get("probable_cause") or "unknown")
                by_cause[cause] = by_cause.get(cause, 0) + 1
                if payload.get("is_anomaly"):
                    stats["anomalies"] += 1
                if out_fh:
                    out_fh.write(json.dumps({
                        "capture_id": item["id"],
                        "device_id": item["device_id"],
                        "filename": item["filename"],
                        "captured_at": item["captured_at"],
                        "edge_ai": payload,
                    }, ensure_ascii=False) + "\n")
                if not args.dry_run:
                    capture = db.query(Capture).filter(Capture.id == item["id"]).first()
                    if not capture:
                        stats["errors"] += 1
                        continue
                    capture.quality_flag = str(report.get("flag") or "")
                    capture.quality_passed = bool(report.get("passed"))
                    capture.blur_score = float(report["blur_score"]) if report.get("blur_score") is not None else None
                    capture.brightness_mean = float(report["brightness_mean"]) if report.get("brightness_mean") is not None else None
                    capture.ai_result = _merge_ai_result(capture.ai_result, payload)
                    upsert_capture_model_result(
                        db,
                        capture_id=capture.id,
                        engine=ENGINE_EDGE_CV,
                        model=str(payload.get("engine") or "edge_cv_v1"),
                        result_kind="qa",
                        result_json=payload,
                        tags=payload.get("tags") or [],
                        confidence=float(payload["confidence"]) if payload.get("confidence") is not None else None,
                        source="edge_backfill",
                    )
                    capture.ai_analyzed_at = datetime.now(timezone.utc)
                    sidecar = image.with_suffix(".json")
                    _write_sidecar(image, payload)
                    capture.sidecar_path = str(sidecar)
                    stats["updated"] += 1
                    if stats["updated"] % max(1, args.commit_every) == 0:
                        db.commit()
                if idx % 250 == 0 or idx == total:
                    elapsed = max(0.1, time.time() - started)
                    print(json.dumps({
                        "progress": idx,
                        "total": total,
                        "rate_per_s": round(idx / elapsed, 2),
                        **stats,
                    }, ensure_ascii=False), flush=True)
            except Exception as exc:
                stats["errors"] += 1
                if out_fh:
                    out_fh.write(json.dumps({
                        "capture_id": capture.id,
                        "device_id": capture.device_id,
                        "filename": capture.filename,
                        "error": str(exc),
                    }, ensure_ascii=False) + "\n")
        if not args.dry_run:
            db.commit()
    finally:
        if executor:
            executor.shutdown(wait=False, cancel_futures=False)
        if out_fh:
            out_fh.close()
        db.close()
    print(json.dumps({
        "status": "dry_run" if args.dry_run else "updated",
        **stats,
        "by_cause": dict(sorted(by_cause.items(), key=lambda item: item[1], reverse=True)),
        "duration_s": round(time.time() - started, 1),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
