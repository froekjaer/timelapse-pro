#!/usr/bin/env python3
"""Migrate real stored Edge QA JSON into capture_model_results."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import and_

HEADEND_ROOT = Path(__file__).resolve().parents[1]
if str(HEADEND_ROOT) not in sys.path:
    sys.path.insert(0, str(HEADEND_ROOT))

from ai.ai_models import CaptureModelResult  # noqa: E402
from ai.model_results import (  # noqa: E402
    ENGINE_EDGE_CV,
    extract_edge_payload,
    upsert_edge_capture_results,
)
from database import Capture, SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--commit-every", type=int, default=250)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    stats = {"scanned": 0, "migrated": 0, "no_edge_payload": 0, "invalid_json": 0}
    try:
        query = (
            db.query(Capture)
            .outerjoin(
                CaptureModelResult,
                and_(
                    CaptureModelResult.capture_id == Capture.id,
                    CaptureModelResult.engine == ENGINE_EDGE_CV,
                ),
            )
            .filter(Capture.ai_result.isnot(None), CaptureModelResult.id.is_(None))
            .order_by(Capture.id.asc())
        )
        if args.device_id:
            query = query.filter(Capture.device_id == args.device_id)
        if args.limit:
            query = query.limit(args.limit)

        for capture in query:
            stats["scanned"] += 1
            try:
                payload = json.loads(capture.ai_result)
            except (TypeError, ValueError):
                stats["invalid_json"] += 1
                continue
            if not extract_edge_payload(payload):
                stats["no_edge_payload"] += 1
                continue
            if not args.dry_run:
                upsert_edge_capture_results(
                    db,
                    capture_id=capture.id,
                    payload=payload,
                    source="legacy_edge_migration",
                )
                if stats["migrated"] and stats["migrated"] % max(1, args.commit_every) == 0:
                    db.commit()
            stats["migrated"] += 1
        if not args.dry_run:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(json.dumps({"status": "dry_run" if args.dry_run else "updated", **stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
