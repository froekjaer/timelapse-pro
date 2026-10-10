#!/usr/bin/env python3
"""Non-destructive source-level preservation gate for TimeLapse Pro.

This gate checks presence of protected source artifacts. It deliberately does not
claim runtime equivalence, GRC acceptance, or deployed device verification.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProtectedArtifact:
    id: str
    owner: str
    path: str
    requirement: str
    purpose: str


PROTECTED = (
    ProtectedArtifact("EDGE-CAPTURE", "edge", "edge/agent.py", "CAP-001", "Autonomous Edge capture/agent"),
    ProtectedArtifact("EDGE-UPDATE", "edge", "edge/update_lifecycle.py", "UPD-009", "Durable Edge rollback"),
    ProtectedArtifact("EDGE-LOCAL-ACCESS", "edge", "edge/scripts/totp-service.py", "CFG-009", "Local Edge management/recovery"),
    ProtectedArtifact("HEADEND-SSH", "headend", "headend/api/ssh_tunnel_terminal_api.py", "CFG-008", "Central authorized browser SSH"),
    ProtectedArtifact("HEADEND-IMAGE", "headend", "headend/tools/build_edge_disk_image.py", "ADM-009", "Golden Edge image builder"),
    ProtectedArtifact("HEADEND-API", "headend", "headend/main.py", "ADM-001", "Central control plane"),
    ProtectedArtifact("UI-CONFIG", "ui", "timelapse-ui/src/pages/GlobalConfigPage.tsx", "ADM-005", "Hierarchical configuration UI"),
)


def check(root: Path) -> dict:
    items = []
    for artifact in PROTECTED:
        file = root / artifact.path
        exists = file.is_file()
        items.append({**asdict(artifact), "present": exists})
    return {
        "schema": "timelapse.preservation.source-gate.v1",
        "root": str(root),
        "status": "PASS_SOURCE_PRESENCE" if all(item["present"] for item in items) else "FAIL_SOURCE_PRESENCE",
        "note": "Source presence is NOT feature parity, tests, security review or runtime verification.",
        "artifacts": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = check(args.root.resolve())
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for item in result["artifacts"]:
            print(f'{"OK" if item["present"] else "MISSING"} {item["owner"]}: {item["id"]} ({item["path"]})')
        print(result["status"])
    return 0 if result["status"] == "PASS_SOURCE_PRESENCE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
