#!/usr/bin/env python3
"""
Check/refresh the local cache of Mission Framework's canonical OP-001
(Mission Operational Preamble) against the authoritative upstream source.

Architecture (Peter, 2026-09-16): "C — canonical Mission Framework source
with controlled local cache/fallback". froekjaer/mission-framework is the
sole authoritative source for OP-001. This script is the explicit, human-
or-agent-triggered refresh mechanism; it is never run silently/automatically
as part of routine repo operations, and it never overwrites the cache
without recording what it did in OP-001.provenance.json.

Freshness states written to provenance.json's "last_check_result":
  VERIFIED - canonical was reachable and its current HEAD SHA was compared
             directly to the cached revision.
  STALE    - canonical was reachable and its HEAD SHA differs from the
             cached revision (evidence of staleness, not a guess).
  UNKNOWN  - canonical could not be reached or returned an unexpected
             response; the previous last_check_result/cached_revision are
             left untouched, since a failed check is not evidence of either
             freshness or staleness.

Usage:
  python3 refresh_op001_cache.py            # check only, do not modify the cache
  python3 refresh_op001_cache.py --refresh  # if STALE, fetch and apply the new content
  python3 refresh_op001_cache.py --json     # machine-readable output on stdout
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CANONICAL_REPOSITORY = "froekjaer/mission-framework"
CANONICAL_PATH = "docs/operational/OP-001-Mission-Operational-Preamble.md"
CANONICAL_BRANCH = "main"

HERE = Path(__file__).resolve().parent
CACHED_FILE = HERE / "OP-001-Mission-Operational-Preamble.md"
PROVENANCE_FILE = HERE / "OP-001.provenance.json"

# Only ever read from api.github.com/raw.githubusercontent.com over HTTPS.
# The commit SHA used to build the raw-content URL always comes from this
# script's own GitHub API call in the same run, never from user input or
# from a previously cached value being blindly re-trusted as "current" -
# see _fetch_canonical_head_sha().
API_REF_URL = f"https://api.github.com/repos/{CANONICAL_REPOSITORY}/git/refs/heads/{CANONICAL_BRANCH}"
RAW_URL_TEMPLATE = f"https://raw.githubusercontent.com/{CANONICAL_REPOSITORY}/{{sha}}/{CANONICAL_PATH}"
HTTP_USER_AGENT = "TimeLapsePro-OP001-Cache/1.0"
REQUEST_TIMEOUT_S = 10

EXPECTED_CONTENT_MARKER = "# OP-001 — Mission Operational Preamble (MOP)"
MIN_EXPECTED_LENGTH = 2000  # sanity floor; the real document is ~9-12 KB


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_provenance() -> dict:
    if not PROVENANCE_FILE.is_file():
        raise SystemExit(
            f"Missing {PROVENANCE_FILE.name} — this cache was not created by this "
            "mechanism. Do not hand-author it; restore it from the last known-good "
            "commit, or run this script with --bootstrap to recreate it fresh from canonical."
        )
    try:
        return json.loads(PROVENANCE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{PROVENANCE_FILE.name} is not valid JSON ({exc}). Refusing to guess its contents. "
            "Restore it from the last known-good commit, or run this script with --bootstrap "
            "to recreate it fresh from canonical (this will not touch the cached content file "
            "unless canonical is reachable)."
        )


def _write_provenance(data: dict) -> None:
    PROVENANCE_FILE.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _fetch_canonical_head_sha() -> str:
    """Returns the current immutable commit SHA of canonical OP-001's branch.

    Raises urllib.error.URLError / TimeoutError / ValueError on any failure -
    callers must treat all of these as "cannot currently verify" (UNKNOWN),
    never as evidence of staleness.
    """
    req = urllib.request.Request(API_REF_URL, headers={"User-Agent": HTTP_USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    sha = payload.get("object", {}).get("sha")
    if not isinstance(sha, str) or len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
        raise ValueError(f"Unexpected ref response, refusing to trust it as a commit SHA: {payload!r}")
    return sha


def _fetch_canonical_content(sha: str) -> str:
    """Fetch OP-001's content pinned to an exact, already-verified commit SHA
    (never a branch name), so the content cannot change between the SHA check
    and the content fetch (no mutable-ref TOCTOU window)."""
    url = RAW_URL_TEMPLATE.format(sha=sha)
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
        content = resp.read().decode("utf-8")
    if EXPECTED_CONTENT_MARKER not in content or len(content) < MIN_EXPECTED_LENGTH:
        raise ValueError(
            "Fetched content failed a basic integrity sanity check (missing expected "
            "heading or implausibly short) - refusing to apply it to the cache."
        )
    return content


def bootstrap() -> dict:
    """Create the cache and provenance file from scratch (first-time setup, or
    recovery after the cache/provenance file was lost/corrupted). Always fetches
    canonical content fresh - never trusts a pre-existing, possibly-tampered
    cache file as a starting point."""
    checked_at = _now_iso()
    head_sha = _fetch_canonical_head_sha()
    content = _fetch_canonical_content(head_sha)
    CACHED_FILE.write_text(content, encoding="utf-8")
    provenance = {
        "canonical_repository": CANONICAL_REPOSITORY,
        "canonical_path": CANONICAL_PATH,
        "cached_revision": head_sha,
        "cached_at": checked_at,
        "last_check_at": checked_at,
        "last_check_result": "VERIFIED",
        "last_check_note": "bootstrapped from canonical HEAD",
    }
    _write_provenance(provenance)
    return {"bootstrapped": True, "cached_revision": head_sha, "checked_at": checked_at}


def check(apply_refresh: bool) -> dict:
    provenance = _load_provenance()
    cached_revision = provenance.get("cached_revision")
    result: dict = {
        "checked_at": _now_iso(),
        "cached_revision": cached_revision,
        "previous_last_check_result": provenance.get("last_check_result"),
        "previous_last_check_at": provenance.get("last_check_at"),
    }

    try:
        head_sha = _fetch_canonical_head_sha()
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        # Cannot currently establish freshness. Do NOT touch cached_revision,
        # do NOT claim VERIFIED, do NOT claim STALE - only that we don't know.
        provenance["last_check_at"] = result["checked_at"]
        provenance["last_check_result"] = "UNKNOWN"
        provenance["last_check_note"] = f"canonical unreachable: {exc}"
        _write_provenance(provenance)
        result.update(
            last_check_result="UNKNOWN",
            reason=str(exc),
            cache_usable=CACHED_FILE.is_file(),
        )
        return result

    result["canonical_head_sha"] = head_sha

    if head_sha == cached_revision:
        provenance["last_check_at"] = result["checked_at"]
        provenance["last_check_result"] = "VERIFIED"
        provenance.pop("last_check_note", None)
        _write_provenance(provenance)
        result.update(last_check_result="VERIFIED", cache_usable=True)
        return result

    # Genuinely stale: canonical was reachable and its HEAD differs from cache.
    provenance["last_check_at"] = result["checked_at"]
    provenance["last_check_result"] = "STALE"
    provenance["last_check_note"] = f"canonical HEAD {head_sha} differs from cached_revision {cached_revision}"
    result.update(last_check_result="STALE", cache_usable=CACHED_FILE.is_file())

    if apply_refresh:
        try:
            new_content = _fetch_canonical_content(head_sha)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            provenance["last_check_note"] += f"; refresh content fetch failed: {exc}"
            _write_provenance(provenance)
            result.update(refreshed=False, refresh_error=str(exc))
            return result

        CACHED_FILE.write_text(new_content, encoding="utf-8")
        provenance["cached_revision"] = head_sha
        provenance["cached_at"] = result["checked_at"]
        provenance["last_check_result"] = "VERIFIED"
        provenance["last_check_note"] = "refreshed to canonical HEAD in this run"
        result.update(refreshed=True, new_cached_revision=head_sha)

    _write_provenance(provenance)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="If STALE, fetch and apply the new canonical content (rewrites the cached body; commit the result yourself).")
    parser.add_argument("--bootstrap", action="store_true", help="Create the cache and provenance file from scratch from canonical HEAD (first-time setup or recovery). Requires canonical to be reachable.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of a human-readable summary.")
    args = parser.parse_args()

    if args.bootstrap:
        result = bootstrap()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            revision = result["cached_revision"]
            print(f"Bootstrapped cache at canonical revision {revision}.")
        return 0

    result = check(apply_refresh=args.refresh)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        state = result["last_check_result"]
        if state == "VERIFIED":
            print(f"VERIFIED - cached OP-001 matches canonical HEAD ({result['cached_revision']}).")
        elif state == "STALE":
            if result.get("refreshed"):
                print(f"STALE -> REFRESHED - cache updated to canonical HEAD {result['new_cached_revision']}. Review and commit the change.")
            else:
                print(
                    f"STALE - canonical HEAD is {result.get('canonical_head_sha')}, cache is pinned to "
                    f"{result['cached_revision']}. Re-run with --refresh to update, or record this as an "
                    "explicit propagation gap if you cannot refresh now."
                )
        else:
            print(
                "UNKNOWN - could not reach canonical Mission Framework to check freshness "
                f"({result.get('reason')}). The cached OP-001 remains usable as-is; its last confirmed "
                f"state was {result.get('previous_last_check_result')!r} as of "
                f"{result.get('previous_last_check_at')!r} against cached_revision "
                f"{result['cached_revision']!r}. This session's governance work may proceed offline, "
                "but this freshness gap should be visible in any consequential Visible Preamble Record."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
