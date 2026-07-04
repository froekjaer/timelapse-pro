#!/usr/bin/env python3
"""
Backfill capture_model_results from legacy captures.ai_result / captures.ai_tags.

This is additive and idempotent. It does not modify captures.ai_result,
captures.ai_tags, capture_tags, or any cloud-bought Gemini data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

HEADEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HEADEND_ROOT.parent
for _path in (str(HEADEND_ROOT), str(REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from ai.model_results import (  # noqa: E402
    ENGINE_EDGE_CV,
    ENGINE_GEMINI_CLOUD,
    ENGINE_HEADEND_OLLAMA,
    upsert_capture_model_result,
)


def _json_obj(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        data = raw
    elif not raw:
        return []
    else:
        try:
            data = json.loads(raw)
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    return list(dict.fromkeys(str(tag).strip().lower() for tag in data if str(tag).strip()))


def _engine_for_payload(payload: dict[str, Any]) -> tuple[str, str]:
    model = str(payload.get("model") or "").strip()
    engine = str(payload.get("engine") or "").strip().lower()
    source = str(payload.get("source") or "").strip().lower()
    model_l = model.lower()
    if model_l == "edge_cv_v1" or source == "edge" or "edge_ai" in payload and not model:
        return ENGINE_EDGE_CV, model or "edge_cv_v1"
    if engine == "cloud" or "gemini" in model_l:
        return ENGINE_GEMINI_CLOUD, model
    return ENGINE_HEADEND_OLLAMA, model


def _confidence(payload: dict[str, Any]) -> float | None:
    value = payload.get("confidence")
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _analysed_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", "postgresql://timelapse@localhost/timelapse_db"))
    parser.add_argument("--site")
    parser.add_argument("--device-id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    stats: dict[str, int] = {"seen": 0, "written": 0, "skipped_no_ai_result": 0}
    by_engine: dict[str, int] = {}
    try:
        sql = """
            SELECT c.id, c.device_id, c.ai_result, c.ai_tags, c.ai_analyzed_at
            FROM captures c
            LEFT JOIN devices d ON d.device_id=c.device_id
            LEFT JOIN sites s ON s.id=d.site_id
            WHERE c.ai_result IS NOT NULL
        """
        params: dict[str, Any] = {}
        if args.site:
            sql += " AND s.name = :site"
            params["site"] = args.site
        if args.device_id:
            sql += " AND c.device_id = :device_id"
            params["device_id"] = args.device_id
        sql += " ORDER BY c.id"
        if args.limit:
            sql += " LIMIT :limit"
            params["limit"] = args.limit
        rows = db.execute(text(sql), params).mappings().all()
        for row in rows:
            stats["seen"] += 1
            payload = _json_obj(row["ai_result"])
            if not payload:
                stats["skipped_no_ai_result"] += 1
                continue
            engine_name, model = _engine_for_payload(payload)
            tags = _json_list(row["ai_tags"])
            if not tags and isinstance(payload.get("tags"), list):
                tags = _json_list(payload.get("tags"))
            if not tags and isinstance(payload.get("approved_tags"), list):
                tags = _json_list(payload.get("approved_tags")) + _json_list(payload.get("new_tags"))
            by_engine[engine_name] = by_engine.get(engine_name, 0) + 1
            if args.dry_run:
                continue
            upsert_capture_model_result(
                db,
                capture_id=int(row["id"]),
                engine=engine_name,
                model=model,
                result_kind="qa" if engine_name == ENGINE_EDGE_CV else "analysis",
                result_json=payload,
                tags=tags,
                confidence=_confidence(payload),
                source="legacy_ai_result_backfill",
                analysed_at=_analysed_at(row["ai_analyzed_at"]),
            )
            stats["written"] += 1
            if stats["written"] % 500 == 0:
                db.commit()
                print(json.dumps({"progress": stats, "by_engine": by_engine}, ensure_ascii=False), flush=True)
        if not args.dry_run:
            db.commit()
        print(json.dumps({"status": "dry_run" if args.dry_run else "updated", **stats, "by_engine": by_engine}, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
