#!/usr/bin/env python3
"""Physical LAB smoke test for TimeLapse AI provider capabilities.

Exercises TEXT and STRUCTURED through the authoritative CapabilityRouter.
No product records, captures, alarms or vocabulary rows are written.
Credential values are never printed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HEADEND_DIR = Path(__file__).resolve().parents[1]
if str(HEADEND_DIR) not in sys.path:
    sys.path.insert(0, str(HEADEND_DIR))

from ai.capability_router import CapabilityRouter  # noqa: E402
from database import get_db  # noqa: E402


def _run_one(router: CapabilityRouter, provider: str, capability: str) -> dict:
    started = time.monotonic()
    try:
        if capability == "text":
            output = router.generate_text(
                function="architecture_smoke",
                provider_order=(provider,),
                prompt="Svar præcis med: TIMELAPSE_OK",
            )
            valid = "TIMELAPSE_OK" in output.content
            detail = {"content": output.content[:200]}
        else:
            output = router.generate_structured(
                function="architecture_smoke",
                provider_order=(provider,),
                prompt=(
                    'Returner kun dette JSON-objekt: '
                    '{"status":"TIMELAPSE_OK","capability":"structured"}'
                ),
            )
            data = output.data if isinstance(output.data, dict) else {}
            valid = (
                data.get("status") == "TIMELAPSE_OK"
                and data.get("capability") == "structured"
            )
            detail = {"data": data}

        return {
            "provider": provider,
            "capability": capability,
            "ok": bool(valid),
            "wall_ms": int((time.monotonic() - started) * 1000),
            "provenance": output.provenance(),
            **detail,
        }
    except Exception as exc:
        return {
            "provider": provider,
            "capability": capability,
            "ok": False,
            "wall_ms": int((time.monotonic() - started) * 1000),
            "error_type": type(exc).__name__,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=("apple", "ollama", "gemini"),
        default=["apple", "ollama", "gemini"],
    )
    parser.add_argument(
        "--capabilities",
        nargs="+",
        choices=("text", "structured"),
        default=["text", "structured"],
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    router = CapabilityRouter(get_db)
    runs = [
        _run_one(router, provider, capability)
        for provider in args.providers
        for capability in args.capabilities
    ]
    report = {
        "smoke_version": 1,
        "providers": args.providers,
        "capabilities": args.capabilities,
        "runs": runs,
        "all_ok": all(row["ok"] for row in runs),
        "note": (
            "LAB capability evidence only. This verifies routing/runtime/structured "
            "contract, not semantic model accuracy or production-scale resource behaviour."
        ),
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    print(encoded)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    return 0 if report["all_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
