#!/usr/bin/env python3
"""
Import a lab-generated apt upgrade list into a Headend-owned update catalog.

Input is text from a LAB/mirror host, not a production Edge decision source:
  apt list --upgradable

The output catalog can be used by reconcile_updates.py and build_os_bundle.py.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


APT_LINE_RE = re.compile(
    r"^(?P<name>[^/]+)/(?P<repos>\S+)\s+"
    r"(?P<available>\S+)\s+"
    r"(?P<arch>\S+)\s+"
    r"\[upgradable from:\s+(?P<installed>[^\]]+)\]"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Headend OS update catalog from lab apt-list text")
    parser.add_argument("--input", required=True, help="Text file with apt list --upgradable output")
    parser.add_argument("--output", required=True, help="Catalog JSON output path")
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--source", default=None, help="Catalog source label")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    packages = parse_apt_list(input_path.read_text())
    catalog = {
        "schema": "dk.froekjaer.timelapse.os_update_catalog.v1",
        "source": args.source or f"lab-import:apt-list:{args.device_id}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device_id": args.device_id,
        "edge_requires_direct_internet": False,
        "edge_may_run_apt_get_upgrade": False,
        "packages": packages,
        "summary": {
            "total": len(packages),
            "os_security": sum(1 for p in packages if p["category"] == "os_security"),
            "os_updates": sum(1 for p in packages if p["category"] == "os_updates"),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "output": str(output_path), **catalog["summary"]}, indent=2))
    return 0


def parse_apt_list(text: str) -> list[dict]:
    packages = []
    seen = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = APT_LINE_RE.match(line)
        if not match:
            continue
        repos = match.group("repos")
        category = "os_security" if "security" in repos else "os_updates"
        key = (match.group("name"), match.group("available"), match.group("arch"))
        if key in seen:
            continue
        seen.add(key)
        packages.append({
            "name": match.group("name"),
            "installed_version": match.group("installed"),
            "available_version": match.group("available"),
            "architecture": match.group("arch"),
            "category": category,
            "severity": "high" if category == "os_security" else "low",
            "source_repo": repos,
        })
    packages.sort(key=lambda p: (p["category"], p["name"]))
    return packages


if __name__ == "__main__":
    raise SystemExit(main())
