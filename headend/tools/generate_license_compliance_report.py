#!/usr/bin/env python3
"""Generate evidence-backed dependency license inventory for TimeLapse Pro."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PERMISSIVE = ("MIT", "APACHE", "BSD", "ISC", "PSF", "ZLIB", "0BSD", "UNLICENSE")
NOTICE = ("MPL", "EPL", "CDDL", "LGPL")
COPYLEFT = ("GPL", "AGPL", "SSPL", "BUSL", "EUPL")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_license(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or "UNKNOWN"


def classify(license_name: str) -> tuple[str, str]:
    upper = license_name.upper()
    if upper == "UNKNOWN" or upper in {"", "NONE"}:
        return "unknown", "License evidence is missing; manual resolution required."
    if "PERMISSION IS HEREBY GRANTED, FREE OF CHARGE" in upper:
        return "permissive", "MIT license text observed; preserve copyright and license notices."
    if "NONFREE" in upper or "PROPRIETARY" in upper:
        return "blocked", "Redistribution/use terms require explicit legal approval."
    if any(token in upper for token in NOTICE):
        return "obligations", "Use is generally possible with notice/source or file-level obligations."
    if any(token in upper for token in COPYLEFT):
        return "review", "Copyleft or source-distribution obligations require deployment review."
    if any(token in upper for token in PERMISSIVE):
        return "permissive", "Permissive license; preserve copyright and license notices."
    return "review", "Unclassified license expression requires manual review."


def python_components() -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []
    for dist in sorted(metadata.distributions(), key=lambda d: (d.metadata.get("Name") or "").lower()):
        name = dist.metadata.get("Name") or "unknown"
        declared = normalize_license(dist.metadata.get("License-Expression") or dist.metadata.get("License"))
        if declared == "UNKNOWN":
            classifiers = [value.removeprefix("License :: ") for value in dist.metadata.get_all("Classifier", [])
                           if value.startswith("License :: ")]
            if classifiers:
                declared = " AND ".join(classifiers)
        license_files = []
        for file in dist.files or []:
            basename = Path(str(file)).name.lower()
            if basename.startswith(("license", "copying", "notice", "copyright")):
                path = Path(dist.locate_file(file))
                if path.is_file():
                    license_files.append({"path": str(file), "sha256": sha256(path)})
        status, rationale = classify(declared)
        components.append({
            "ecosystem": "pypi", "name": name, "version": dist.version,
            "purl": f"pkg:pypi/{name.lower().replace('_', '-')}@{dist.version}",
            "license_declared": declared, "license_evidence": license_files,
            "evidence_source": "installed-python-metadata", "status": status,
            "rationale": rationale,
        })
    return components


def npm_components(lock_path: Path) -> list[dict[str, Any]]:
    if not lock_path.is_file():
        return []
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    components = []
    for package_path, package in sorted((lock.get("packages") or {}).items()):
        if not package_path or not package_path.startswith("node_modules/"):
            continue
        name = package_path.removeprefix("node_modules/")
        version = str(package.get("version") or "unknown")
        declared = normalize_license(package.get("license"))
        status, rationale = classify(declared)
        components.append({
            "ecosystem": "npm", "name": name, "version": version,
            "purl": f"pkg:npm/{name}@{version}", "license_declared": declared,
            "license_evidence": [{"source": "package-lock.json", "integrity": package.get("integrity")}],
            "evidence_source": "npm-lockfile", "status": status, "rationale": rationale,
            "development": bool(package.get("dev", False)),
        })
    return components


def homebrew_components() -> list[dict[str, Any]]:
    try:
        proc = subprocess.run(["brew", "info", "--json=v2", "--installed"], capture_output=True,
                              text=True, timeout=120, check=False)
        data = json.loads(proc.stdout) if proc.returncode == 0 else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []
    result = []
    for formula in data.get("formulae", []):
        installed = formula.get("installed") or [{}]
        version = str(installed[0].get("version") or formula.get("versions", {}).get("stable") or "unknown")
        declared = normalize_license(formula.get("license"))
        status, rationale = classify(declared)
        result.append({"ecosystem": "homebrew", "name": formula.get("name"), "version": version,
                       "purl": f"pkg:brew/{formula.get('name')}@{version}", "license_declared": declared,
                       "license_evidence": [{"source": "brew-info-json-v2", "homepage": formula.get("homepage")}],
                       "evidence_source": "installed-homebrew-metadata", "status": status, "rationale": rationale})
    return result


def debian_components() -> list[dict[str, Any]]:
    try:
        proc = subprocess.run(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${Architecture}\n"],
                              capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    result = []
    for line in proc.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        binary_name, version, architecture = fields
        name = binary_name.split(":", 1)[0]
        copyright_path = Path("/usr/share/doc") / name / "copyright"
        evidence = []
        licenses = []
        if copyright_path.is_file():
            evidence.append({"path": str(copyright_path), "sha256": sha256(copyright_path)})
            try:
                text = copyright_path.read_text(encoding="utf-8", errors="replace")
                licenses = [match.strip() for match in re.findall(r"(?mi)^License:\s*([^\n]+)", text)]
            except OSError:
                pass
        declared = normalize_license(" AND ".join(dict.fromkeys(licenses)))
        status, rationale = classify(declared)
        result.append({"ecosystem": "deb", "name": binary_name, "version": version,
                       "purl": f"pkg:deb/ubuntu/{name}@{version}?arch={architecture}",
                       "license_declared": declared, "license_evidence": evidence,
                       "evidence_source": "dpkg-status-and-copyright", "status": status, "rationale": rationale})
    return result


def command_evidence(name: str, command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
        output = (result.stdout + "\n" + result.stderr).strip()
        evidence = {"name": name, "command": command, "available": result.returncode == 0,
                    "returncode": result.returncode, "output": output[:30000]}
        if name == "ffmpeg":
            lower = output.lower()
            if "--enable-nonfree" in lower:
                evidence.update(status="blocked", license_observed="NONFREE")
            elif "--enable-gpl" in lower:
                evidence.update(status="review", license_observed="GPL-2.0-or-later")
            else:
                evidence.update(status="obligations", license_observed="LGPL-2.1-or-later")
        elif re.search(r"GNU\s+GENERAL\s+PUBLIC\s+LICENSE", output, re.IGNORECASE):
            evidence.update(status="review", license_observed="GPL (version requires source evidence)")
        return evidence
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": name, "command": command, "available": False, "status": "unknown", "error": str(exc)}


def runtime_tools() -> list[dict[str, Any]]:
    return [
        command_evidence("ffmpeg", ["ffmpeg", "-hide_banner", "-version"]),
        command_evidence("gphoto2", ["gphoto2", "--version"]),
        command_evidence("nginx", ["nginx", "-V"]),
        command_evidence("ollama", ["ollama", "--version"]),
        command_evidence("postgresql", ["psql", "--version"]),
    ]


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# TimeLapse Pro - License Compliance Evidence Report", "",
        f"Generated: `{report['generated_at']}`", "",
        "> This is an engineering compliance assessment, not legal advice. Unknown and review items require resolution before redistribution.", "",
        "## Executive Summary", "",
        f"- Components inventoried: **{summary['component_count']}**",
        f"- Permissive: **{summary.get('permissive', 0)}**",
        f"- Obligations: **{summary.get('obligations', 0)}**",
        f"- Manual review: **{summary.get('review', 0)}**",
        f"- Unknown: **{summary.get('unknown', 0)}**",
        f"- Blocked: **{summary.get('blocked', 0)}**", "",
        f"**Overall status: {report['overall_status'].upper()}**", "",
        "## Runtime Tools", "",
        "| Tool | Available | Observed license | Status |", "|---|---:|---|---|",
    ]
    for tool in report["runtime_tools"]:
        lines.append(f"| {tool['name']} | {tool.get('available', False)} | {tool.get('license_observed', 'not asserted')} | {tool.get('status', 'inventory-only')} |")
    lines += ["", "## Components Requiring Attention", "",
              "| Ecosystem | Component | Version | License | Status |", "|---|---|---|---|---|"]
    for item in report["components"]:
        if item["status"] != "permissive":
            lines.append(f"| {item['ecosystem']} | {item['name']} | {item['version']} | {item['license_declared']} | {item['status']} |")
    lines += ["", "## Evidence and Policy", "",
              "- Python evidence comes from installed distribution metadata and hashes of installed LICENSE/COPYING/NOTICE files.",
              "- npm evidence comes from the committed lockfile, including package integrity values.",
              "- Runtime-tool evidence is captured from the actual executable on the machine generating this report.",
              "- Copyleft does not automatically mean prohibited; distribution model and obligations must be reviewed.",
              "- Codec patent/licensing questions are separate from open-source copyright licenses.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    script_path = Path(__file__).resolve()
    default_repo = script_path.parents[2] if len(script_path.parents) > 2 else Path.cwd()
    parser.add_argument("--repo", type=Path, default=default_repo)
    parser.add_argument("--output-dir", type=Path, default=Path("Dokumentation/evidence/licenses"))
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output_dir if args.output_dir.is_absolute() else repo / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    components = (python_components() + npm_components(repo / "timelapse-ui" / "package-lock.json")
                  + homebrew_components() + debian_components())
    counts = Counter(item["status"] for item in components)
    tools = runtime_tools()
    tool_statuses = {item.get("status") for item in tools}
    overall = "blocked" if "blocked" in counts or "blocked" in tool_statuses else (
        "review_required" if counts.get("unknown") or counts.get("review") or "review" in tool_statuses else "compliant_with_obligations"
    )
    report = {
        "schema": "dk.froekjaer.timelapse.license-evidence.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_python": metadata.version("pip") if _has_distribution("pip") else "unknown",
        "overall_status": overall,
        "summary": {"component_count": len(components), **dict(counts)},
        "components": components,
        "runtime_tools": tools,
    }
    json_path = output / "license-compliance-report.json"
    md_path = output / "license-compliance-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "summary": report["summary"], "overall_status": overall}))
    return 2 if overall == "blocked" else 0


def _has_distribution(name: str) -> bool:
    try:
        metadata.version(name)
        return True
    except metadata.PackageNotFoundError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
